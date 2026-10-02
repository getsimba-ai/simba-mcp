"""Measurements must describe the wire, preserve behaviour and exclude caller data."""

import asyncio
import gzip
import hashlib
import json
import sys
from types import SimpleNamespace

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from starlette.testclient import TestClient

from simba_mcp import performance, runtime, server, telemetry
from simba_mcp.api_client import CALLER_API_KEY, SimbaAPIClient
from simba_mcp.benchmark import benchmark


@pytest.fixture
def anyio_backend():
    return "asyncio"


def install_backend(monkeypatch, handler):
    async def get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://example.test", transport=httpx.MockTransport(handler)
            )
        return self._client

    monkeypatch.setattr(SimbaAPIClient, "_get_client", get_client)
    monkeypatch.setattr(runtime, "_serving_http", runtime._serving_http)


def wire_call(client, tool="get_model_results", arguments=None):
    return client.post(
        "/",
        headers={
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer PRIVATE-CREDENTIAL",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool,
                "arguments": arguments
                if arguments is not None
                else {
                    "model_hash": "PRIVATE-MODEL",
                    "channels": ["PRIVATE-CHANNEL"],
                    "max_response_bytes": 100000,
                },
            },
        },
    )


def test_surface_matches_real_wire_and_never_calls_backend(monkeypatch, tmp_path):
    async def forbidden(*args, **kwargs):
        pytest.fail("surface inspection must not call the backend")

    monkeypatch.setattr(SimbaAPIClient, "_get_client", forbidden)
    monkeypatch.setattr(runtime, "_serving_http", False)
    initial, raw = performance.capture_surface()
    report = performance.surface_report()
    tools = json.loads(raw)["result"]["tools"]
    assert report["tools_list_http_body"]["utf8_bytes"] == len(raw)
    assert report["tools_list_http_body"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert [t["name"] for t in report["tools"]] == [t["name"] for t in tools]
    assert report["tool_count"] == len(server.TOOLS)
    assert "inputSchema" in report["tools"][0]["fields"]
    assert "outputSchema" in report["tools"][0]["fields"]
    assert report["tools_list_http_body"]["estimated_tokens"] is None
    assert report["provider_usage"]["input_tokens"] is None
    assert report["server_instructions"]["utf8_bytes"] == len(
        performance.compact(json.loads(initial)["result"]["instructions"]).encode("utf-8")
    )
    assert runtime._serving_http is False
    assert performance.main(["--output-dir", str(tmp_path)]) == 0
    assert json.loads((tmp_path / "surface.json").read_text())["tool_count"] == len(tools)
    assert "not model usage or billing" in (tmp_path / "surface.md").read_text()


def test_tokenizer_is_explicit_and_fields_remain_independent(monkeypatch):
    seen = []

    class Encoder:
        def encode(self, text, *, disallowed_special):
            seen.append(text)
            assert disallowed_special == ()
            return [0] * 7

    def get_encoding(name):
        assert name == "o200k_base"
        return Encoder()

    monkeypatch.setitem(sys.modules, "tiktoken", SimpleNamespace(get_encoding=get_encoding))
    report = performance.surface_report("o200k_base")
    assert report["tools_list_http_body"]["estimated_tokens"] == 7
    assert report["tools"][0]["total"]["estimated_tokens"] == 7
    assert len(seen) > len(server.TOOLS)
    assert report["tokenizer"]["status"] == "representation_estimate"


@pytest.mark.parametrize("scenario", ["ok", "refused", "malformed", "invalid_arguments"])
def test_enabled_metrics_preserve_wire_and_exclude_private_values(monkeypatch, scenario):
    def handle(request):
        if scenario == "refused":
            return httpx.Response(409, json={"error": "PRIVATE-ERROR", "code": "PRIVATE-CODE"})
        if scenario == "malformed":
            return httpx.Response(
                200, content=b"PRIVATE-BROKEN", headers={"content-type": "application/json"}
            )
        return httpx.Response(
            200,
            json={
                "channel_summary": [
                    {"Channel": "PRIVATE-CHANNEL", "Revenue": 42, "note": "PRIVATE-BODY"}
                ]
            },
        )

    install_backend(monkeypatch, handle)
    events, bodies = [], []
    for sink in (None, events.append):
        with telemetry.use_sink(sink), TestClient(server._create_app()) as client:
            response = wire_call(client, arguments={} if scenario == "invalid_arguments" else None)
            bodies.append(response.content)
    assert bodies[0] == bodies[1]
    assert len(events) == 1
    event = events[0]
    assert "PRIVATE" not in json.dumps(event)
    assert event["outcome"] == ("ok" if scenario == "ok" else "refused")
    assert event["backend_attempt_count"] == (0 if scenario == "invalid_arguments" else 1)
    assert event["content_json_bytes"] > 0
    assert event["call_tool_result_json_bytes"] > event["content_json_bytes"]
    assert not event["measurement_failed"]
    if scenario == "ok":
        assert event["phase_seconds"]["result_filter"] > 0
        assert event["phase_seconds"]["result_cap_serialisation"] > 0


def test_download_counts_distinguish_compressed_and_decoded_bytes(monkeypatch):
    raw = json.dumps({"rows": ["synthetic" * 50] * 50}).encode()
    compressed = gzip.compress(raw)

    def handle(request):
        return httpx.Response(
            200,
            headers={"content-type": "application/json", "content-encoding": "gzip"},
            stream=httpx.ByteStream(compressed),
        )

    install_backend(monkeypatch, handle)
    events = []
    with telemetry.use_sink(events.append), TestClient(server._create_app()) as client:
        assert not wire_call(client).json()["result"].get("isError")
    attempt = events[0]["backend_attempts"][0]
    assert attempt["downloaded_body_bytes"] == len(compressed)
    assert attempt["decoded_body_bytes"] == len(raw)


@pytest.mark.anyio
async def test_retries_count_attempts_without_replaying_writes(monkeypatch):
    monkeypatch.setattr("simba_mcp.api_client.BACKOFF_BASE", 0)
    received = []

    def handle(request):
        received.append(request.method)
        return httpx.Response(503, json={"error": "private response"})

    api = SimbaAPIClient("https://example.test", "synthetic")
    api._client = httpx.AsyncClient(base_url=api.base_url, transport=httpx.MockTransport(handle))
    events = []
    try:
        with telemetry.observe("list_models", events.append):
            result = await api.list_models()
        assert result["_status_code"] == 503
        assert events[-1]["backend_attempt_count"] == 3
        with telemetry.observe("create_project", events.append):
            await api.create_project("PRIVATE-NAME")
        assert events[-1]["backend_attempt_count"] == 1
        assert received == ["GET", "GET", "GET", "POST"]
        assert "PRIVATE" not in json.dumps(events)
    finally:
        await api.close()


@pytest.mark.anyio
async def test_transport_error_and_cancellation_are_observed_and_propagated(monkeypatch):
    monkeypatch.setattr("simba_mcp.api_client.BACKOFF_BASE", 0)

    async def fail(request):
        raise httpx.ConnectError("PRIVATE-URL")

    api = SimbaAPIClient("https://example.test", "synthetic")
    api._client = httpx.AsyncClient(base_url=api.base_url, transport=httpx.MockTransport(fail))
    events = []
    with telemetry.observe("list_models", events.append):
        result = await api.list_models()
    assert result["_status_code"] == 503
    assert all(e["outcome"] == "transport_error" for e in events[-1]["backend_attempts"])
    await api.close()

    started = asyncio.Event()

    async def wait(request):
        started.set()
        await asyncio.Event().wait()

    api._client = httpx.AsyncClient(base_url=api.base_url, transport=httpx.MockTransport(wait))
    context = SimpleNamespace(
        headers={}, request_context=SimpleNamespace(lifespan_context=runtime.AppContext(api))
    )
    monkeypatch.setattr(runtime, "_serving_http", False)
    token = CALLER_API_KEY.set(None)
    try:
        with telemetry.use_sink(events.append):
            task = asyncio.create_task(server.mcp.call_tool("list_models", {}, context))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert events[-1]["outcome"] == "cancelled"
        assert events[-1]["backend_attempts"][0]["outcome"] == "cancelled"
        assert "PRIVATE" not in json.dumps(events)
        assert telemetry._observation.get() is None
    finally:
        CALLER_API_KEY.reset(token)
        await api.close()


@pytest.mark.anyio
async def test_concurrent_callers_keep_credentials_and_metrics_separate(monkeypatch):
    seen = []

    async def handle(request):
        await asyncio.sleep(0)
        seen.append(request.headers["authorization"])
        return httpx.Response(200, json={"echo": request.headers["authorization"]})

    api = SimbaAPIClient("https://example.test", "unused")
    api._client = httpx.AsyncClient(base_url=api.base_url, transport=httpx.MockTransport(handle))
    monkeypatch.setattr(runtime, "_serving_http", True)
    records = [[], []]

    async def run(index):
        ctx = SimpleNamespace(
            headers={"Authorization": f"Bearer PRIVATE-{index}"},
            request_context=SimpleNamespace(lifespan_context=runtime.AppContext(api)),
        )
        with telemetry.use_sink(records[index].append):
            return await server.mcp.call_tool("list_models", {}, ctx)

    try:
        results = await asyncio.gather(run(0), run(1))
        assert [r.structured_content["echo"] for r in results] == [
            "Bearer PRIVATE-0",
            "Bearer PRIVATE-1",
        ]
        assert set(seen) == {"Bearer PRIVATE-0", "Bearer PRIVATE-1"}
        assert all(len(r) == 1 and r[0]["backend_attempt_count"] == 1 for r in records)
        assert "PRIVATE" not in json.dumps(records)
    finally:
        await api.close()


@pytest.mark.anyio
async def test_unknown_tool_and_broken_sink_do_not_leak_or_change_errors():
    events = []
    with telemetry.use_sink(events.append), pytest.raises(ToolError):
        await server.mcp.call_tool("PRIVATE-NAME", {})
    assert events[0]["tool"] == "other"
    assert "PRIVATE" not in json.dumps(events)

    def broken(event):
        raise RuntimeError("PRIVATE-SECRET")

    with telemetry.use_sink(broken):
        result = await server.mcp.call_tool("get_model_results", {})
    assert result.is_error
    assert result.structured_content["code"] == "invalid_arguments"


def test_route_labels_are_fixed_and_attempt_detail_is_bounded():
    assert (
        telemetry.route_label("/api/v1/recipe-draft-template?family=mmm&uploaded_file_id=SECRET")
        == "/api/v1/recipe-draft-template"
    )
    assert telemetry.route_label("/api/v1/models/SECRET/results") == "/api/v1/models/{id}/results"
    assert telemetry.route_label("/api/v1/SECRET") == "other"
    events = []
    with telemetry.observe("list_models", events.append):
        for _ in range(telemetry.MAX_ATTEMPT_DETAILS + 3):
            with telemetry.backend_attempt("SECRET-METHOD", "/SECRET-ROUTE"):
                pass
    assert len(events[0]["backend_attempts"]) == telemetry.MAX_ATTEMPT_DETAILS
    assert events[0]["dropped_attempt_details"] == 3
    assert "SECRET" not in json.dumps(events)


def test_default_off_and_stderr_opt_in(monkeypatch, capsys):
    monkeypatch.delenv("SIMBA_MCP_METRICS", raising=False)
    assert telemetry.get_sink() is None
    monkeypatch.setenv("SIMBA_MCP_METRICS", "stderr")
    with telemetry.observe("list_models", telemetry.get_sink()):
        pass
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["tool"] == "list_models"


@pytest.mark.anyio
async def test_benchmark_is_synthetic_and_preserves_results():
    report = await benchmark(2)
    assert report["provider_usage"] is None
    assert len(report["fixture_sha256"]) == 64
    for case in report["cases"]:
        assert case["unchanged_result"]
        assert case["example_observation"]["backend_attempt_count"] == 1
        for mode in case["measurements"].values():
            assert mode["warm_seconds"]["samples"] == 2
            assert mode["first_iteration_seconds"] > 0
