"""Bounded streamed response handling without a live backend."""

import asyncio
import gzip
import tracemalloc
import zlib
from contextlib import suppress

import anyio
import httpx
import pytest

from simba_mcp import telemetry
from simba_mcp.api_client import SimbaAPIClient
from simba_mcp.runtime import _response_byte_limit


@pytest.fixture
def anyio_backend():
    return "asyncio"


class ChunkStream(httpx.AsyncByteStream):
    def __init__(self, chunks, *, started=None, block_after_first=False):
        self.chunks = chunks
        self.started = started
        self.block_after_first = block_after_first
        self.consumed = 0
        self.closed = False
        self.release = anyio.Event()

    async def __aiter__(self):
        for index, chunk in enumerate(self.chunks):
            if self.started is not None:
                self.started.set()
            if index == 1 and self.block_after_first:
                await self.release.wait()
            self.consumed += len(chunk)
            yield chunk

    async def aclose(self):
        self.closed = True


def _client(handler, *, encoded=None, decoded=None):
    client = SimbaAPIClient(
        "https://synthetic.invalid",
        "synthetic-key",
        max_encoded_bytes=encoded,
        max_decoded_bytes=decoded,
    )
    client._client = httpx.AsyncClient(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
    )
    return client


@pytest.mark.anyio
@pytest.mark.parametrize("content_length", [None, "1"])
async def test_actual_streamed_bytes_enforce_limit_without_trusting_content_length(content_length):
    body = b"x" * (2 * 1024 * 1024)
    stream = ChunkStream([body[: 64 * 1024], body[64 * 1024 :]])
    headers = {"content-type": "application/json"}
    if content_length is not None:
        headers["content-length"] = content_length
    client = _client(
        lambda _: httpx.Response(200, headers=headers, stream=stream),
        encoded=32 * 1024,
    )
    try:
        result = await client.get_schema()
        assert result["_status_code"] == 413
        assert result["limit"] == "encoded_bytes"
        assert "no partial data" not in result["error"]
        assert stream.closed
        assert stream.consumed < len(body)
    finally:
        await client.close()


@pytest.mark.anyio
async def test_refused_body_telemetry_marks_refusal_and_counts_only_parsed_bytes():
    stream = ChunkStream([b'{"x":"' + b"z" * 2048 + b'"}'])
    client = _client(lambda _: httpx.Response(200, stream=stream), decoded=32)
    events = []
    try:
        with telemetry.observe("get_schema", events.append):
            result = await client.get_schema()
        assert result["_status_code"] == 413
        attempt = events[0]["backend_attempts"][0]
        assert attempt["outcome"] == "refused"
        assert attempt["decoded_body_bytes"] == 0
    finally:
        await client.close()


@pytest.mark.anyio
async def test_auxiliary_memory_stays_bounded_for_large_synthetic_stream():
    # The source fixture is allocated before tracing. The measured peak covers
    # reader-side buffering while a 32 MiB response is refused at 32 KiB.
    chunks = [b"x" * (64 * 1024) for _ in range(512)]
    stream = ChunkStream(chunks)
    client = _client(
        lambda _: httpx.Response(200, stream=stream),
        encoded=32 * 1024,
    )
    tracemalloc.start()
    tracemalloc.reset_peak()
    try:
        result = await client.get_schema()
        _, peak = tracemalloc.get_traced_memory()
        assert result["_status_code"] == 413
        assert stream.consumed < sum(map(len, chunks))
        assert peak < 2 * 1024 * 1024
    finally:
        tracemalloc.stop()
        await client.close()


@pytest.mark.anyio
async def test_content_length_hint_refuses_early_and_closes_stream():
    stream = ChunkStream([b"small body"])
    client = _client(
        lambda _: httpx.Response(
            200,
            headers={"content-type": "application/json", "content-length": "1000"},
            stream=stream,
        ),
        encoded=100,
    )
    try:
        result = await client.get_schema()
        assert result["_status_code"] == 413
        assert stream.consumed == 0
        assert stream.closed
    finally:
        await client.close()


@pytest.mark.anyio
async def test_gzip_expansion_is_bounded_before_json_parsing():
    raw = b"{" + b'"x":"' + b"z" * (2 * 1024 * 1024) + b'"}'
    compressed = gzip.compress(raw)
    stream = ChunkStream([compressed])
    client = _client(
        lambda _: httpx.Response(
            200,
            headers={"content-type": "application/json", "content-encoding": "gzip"},
            stream=stream,
        ),
        decoded=4096,
    )
    try:
        result = await client.get_schema()
        assert result["_status_code"] == 413
        assert result["limit"] == "decoded_bytes"
        assert stream.closed
    finally:
        await client.close()


@pytest.mark.anyio
async def test_prebuffered_response_refuses_when_encoded_limit_cannot_be_verified():
    raw = b'{"x":"' + b"z" * (64 * 1024) + b'"}'
    compressed = gzip.compress(raw)
    client = _client(
        lambda _: httpx.Response(
            200,
            headers={"content-type": "application/json", "content-encoding": "gzip"},
            content=compressed,
        ),
        decoded=1024,
    )
    try:
        result = await client.get_schema()
        assert result["_status_code"] == 502
        assert "response was buffered" in result["error"]
    finally:
        await client.close()


@pytest.mark.anyio
async def test_concatenated_gzip_members_are_refused_instead_of_partially_parsed():
    stream = ChunkStream([gzip.compress(b'{"first":true}') + gzip.compress(b'{"second":true}')])
    client = _client(
        lambda _: httpx.Response(
            200,
            headers={"content-type": "application/json", "content-encoding": "gzip"},
            stream=stream,
        ),
        decoded=1024,
    )
    events = []
    try:
        with telemetry.observe("get_schema", events.append):
            result = await client.get_schema()
        assert result["_status_code"] == 502
        assert "trailing or concatenated" in result["error"]
        assert stream.closed
        attempt = events[0]["backend_attempts"][0]
        assert attempt["outcome"] == "refused"
        assert attempt["decoded_body_bytes"] == 0
    finally:
        await client.close()


@pytest.mark.anyio
async def test_utf8_csv_preserves_text_and_byte_count_not_character_count():
    body = "label,value\n£,1\n".encode()
    client = _client(
        lambda _: httpx.Response(
            200,
            headers={"content-type": "text/csv; charset=utf-8"},
            stream=ChunkStream([body[:5], body[5:]]),
        ),
        encoded=len(body),
    )
    try:
        result = await client.get_schema()
        assert result == {"format": "csv", "content": "label,value\n£,1\n"}
    finally:
        await client.close()


@pytest.mark.anyio
async def test_large_json_and_error_bodies_refuse_without_partial_payload():
    for status in (200, 400):
        stream = ChunkStream([b'{"error":"' + b"p" * 64 * 1024 + b'"}'])
        client = _client(
            lambda _, status=status, stream=stream: httpx.Response(
                status,
                headers={"content-type": "application/json"},
                stream=stream,
            ),
            decoded=1024,
        )
        try:
            result = await client.get_schema()
            assert result["_status_code"] == 413
            assert result["_error_code"] == "payload_too_large"
            assert "p" * 20 not in result["error"]
            assert stream.closed
        finally:
            await client.close()


@pytest.mark.anyio
async def test_limited_response_closes_and_next_request_succeeds_on_same_client():
    oversized = ChunkStream([b"x" * 64 * 1024])
    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, stream=oversized)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            stream=ChunkStream([b'{"ok":true}']),
        )

    client = _client(handler, encoded=1024)
    try:
        assert (await client.get_schema())["_status_code"] == 413
        assert oversized.closed
        assert await client.get_schema() == {"ok": True}
    finally:
        await client.close()


@pytest.mark.anyio
async def test_real_local_pool_recovers_after_oversized_response():
    connections = 0

    async def handle(reader, writer):
        nonlocal connections
        connections += 1
        connection_number = connections
        try:
            await reader.readuntil(b"\r\n\r\n")
            if connection_number == 1:
                writer.write(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: 1048576\r\n\r\n"
                )
                await writer.drain()
                for _ in range(16):
                    writer.write(b"x" * (64 * 1024))
                    await writer.drain()
            else:
                body = b'{"ok":true}'
                writer.write(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: application/json\r\n"
                    + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
                await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()
            with suppress(ConnectionError, OSError):
                await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client = SimbaAPIClient(f"http://127.0.0.1:{port}", "synthetic-key", max_encoded_bytes=1024)
    client._client = httpx.AsyncClient(
        base_url=client.base_url,
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
    )
    try:
        assert (await client.get_schema())["_status_code"] == 413
        assert await client.get_schema() == {"ok": True}
        assert connections == 2
    finally:
        await client.close()
        server.close()
        await server.wait_closed()


@pytest.mark.anyio
async def test_cancellation_closes_stream_and_same_client_remains_usable():
    started = anyio.Event()
    stream = ChunkStream([b"first", b"second"], started=started, block_after_first=True)
    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, stream=stream)
        return httpx.Response(200, json={"ok": True})

    client = _client(handler)
    try:
        with anyio.move_on_after(1) as timeout:
            async with anyio.create_task_group() as group:
                group.start_soon(client.get_schema)
                await started.wait()
                group.cancel_scope.cancel()
        assert not timeout.cancel_called
        assert stream.closed
        stream.release.set()
        assert await client.get_schema() == {"ok": True}
    finally:
        stream.release.set()
        await client.close()


def test_response_byte_limit_configuration_is_opt_in_and_validated(monkeypatch):
    monkeypatch.delenv("SIMBA_API_MAX_ENCODED_BYTES", raising=False)
    assert _response_byte_limit("SIMBA_API_MAX_ENCODED_BYTES") is None
    monkeypatch.setenv("SIMBA_API_MAX_ENCODED_BYTES", "4096")
    assert _response_byte_limit("SIMBA_API_MAX_ENCODED_BYTES") == 4096
    for invalid in ("0", "-1", "one-megabyte"):
        monkeypatch.setenv("SIMBA_API_MAX_ENCODED_BYTES", invalid)
        with pytest.raises(ValueError, match="positive integer"):
            _response_byte_limit("SIMBA_API_MAX_ENCODED_BYTES")


@pytest.mark.anyio
@pytest.mark.parametrize("coding", ["gzip", "deflate", "raw-deflate"])
@pytest.mark.parametrize("bounded", [False, True])
@pytest.mark.parametrize("oversized", [False, True])
async def test_compression_compatibility_and_decoded_boundary(coding, bounded, oversized):
    raw = b'{"x":"' + b"z" * 65536 + b'"}'
    if coding == "gzip":
        encoded = gzip.compress(raw)
    else:
        compressor = zlib.compressobj(wbits=-15 if coding == "raw-deflate" else 15)
        encoded = compressor.compress(raw) + compressor.flush()
    requests = []
    stream = ChunkStream([encoded[:1], encoded[1:]] if bounded else [encoded])

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "content-encoding": "deflate" if coding == "raw-deflate" else coding,
            },
            stream=stream,
        )

    client = _client(
        handler,
        encoded=len(raw) if bounded else None,
        decoded=len(raw) - int(oversized) if bounded else None,
    )
    try:
        result = await client.get_schema()
        if bounded and oversized:
            assert result["_status_code"] == 413
            assert result["limit"] == "decoded_bytes"
        else:
            assert result == {"x": "z" * 65536}
        assert "gzip" in requests[0].headers["accept-encoding"]
        if not bounded:
            assert (
                requests[0].headers["accept-encoding"] == client._client.headers["accept-encoding"]
            )
        assert stream.closed
    finally:
        await client.close()
