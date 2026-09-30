"""Synthetic transport faults and bounded caller admission, with no backend access."""

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from simba_mcp.api_client import CALLER_API_KEY, SimbaAPIClient
from simba_mcp.request_budget import (
    RequestAdmission,
    RequestBudget,
    RequestDeadline,
    RequestOverload,
    RequestPolicy,
    policy_from_json,
    retry_after_seconds,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def policy(**updates):
    values = {
        "total_seconds": 1,
        "connect_seconds": 0.5,
        "read_seconds": 0.5,
        "write_seconds": 0.5,
        "pool_seconds": 0.5,
        "max_active": 2,
        "max_active_per_caller": 1,
        "max_queued": 4,
        "max_queued_per_caller": 2,
    }
    return RequestPolicy(**(values | updates))


def client(handler, **updates):
    instance = SimbaAPIClient(
        "https://synthetic.invalid", "synthetic", request_policy=policy(**updates)
    )
    instance._client = httpx.AsyncClient(
        base_url=instance.base_url, transport=httpx.MockTransport(handler)
    )
    return instance


def test_fake_clock_budget_counts_attempt_time_and_backoff(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("simba_mcp.request_budget.time.monotonic", lambda: clock[0])
    budget = RequestBudget(10)
    clock[0] += 6
    budget.retry(3)
    clock[0] += 3
    assert budget.remaining() == 1
    with pytest.raises(RequestDeadline):
        budget.retry(1)
    clock[0] += 1
    with pytest.raises(RequestDeadline):
        budget.remaining()


@pytest.mark.parametrize(
    "header,expected",
    [
        ("5", 5),
        ("Tue, 29 Sep 2026 12:00:05 GMT", 5),
        ("Tue, 29 Sep 2026 11:00:00 GMT", 0),
        ("nonsense", None),
        ("-1", None),
    ],
)
def test_retry_after_formats(header, expected):
    assert retry_after_seconds(header, datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)) == expected


@pytest.mark.anyio
async def test_retry_after_outside_budget_refuses_without_second_send():
    calls = []
    instance = client(
        lambda request: calls.append(request) or httpx.Response(429, headers={"retry-after": "10"})
    )
    try:
        result = await instance.get_schema()
        assert result["_error_code"] == "request_deadline_exceeded"
        assert len(calls) == 1
        assert instance._admission.active == 0
    finally:
        await instance.close()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fault",
    [
        httpx.ConnectTimeout,
        httpx.PoolTimeout,
        httpx.ReadTimeout,
        httpx.ReadError,
        httpx.RemoteProtocolError,
        429,
        500,
        503,
    ],
)
async def test_read_faults_retry_but_mutations_send_once(fault, monkeypatch):
    monkeypatch.setattr("simba_mcp.api_client.random.uniform", lambda *_: 0)
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            if isinstance(fault, type):
                raise fault("synthetic")
            return httpx.Response(fault)
        return httpx.Response(200, json={"ok": True})

    instance = client(handler)
    try:
        assert await instance.get_schema() == {"ok": True}
        assert len(calls) == 2
        calls.clear()
        result = await instance.create_model({"submission_key": "exact"})
        assert result["_status_code"] >= 400
        assert len(calls) == 1
        assert json.loads(calls[0].content) == {"submission_key": "exact"}
        assert "reconcile" in result["_next_action"].lower()
    finally:
        await instance.close()


class _DisconnectingStream(httpx.AsyncByteStream):
    def __init__(self):
        self.closed = False

    async def __aiter__(self):
        yield b'{"partial":'
        raise httpx.ReadError("synthetic disconnect")

    async def aclose(self):
        self.closed = True


@pytest.mark.anyio
async def test_disconnect_mid_read_closes_stream_retries_get_and_reuses_client(monkeypatch):
    """A mid-body disconnect closes that stream, retries a safe read, and leaves the client usable.

    The final read is a new call after the recovered GET and the single-send mutation
    failure. It is not the automatic retry of the disconnected GET.
    """
    monkeypatch.setattr("simba_mcp.api_client.random.uniform", lambda *_: 0)
    calls = []
    disconnected = []
    seen = {"GET": 0, "POST": 0}

    def handler(request):
        calls.append(request)
        seen[request.method] = seen.get(request.method, 0) + 1
        if request.method == "GET" and seen["GET"] == 1:
            stream = _DisconnectingStream()
            disconnected.append(stream)
            return httpx.Response(200, stream=stream)
        if request.method == "POST" and seen["POST"] == 1:
            stream = _DisconnectingStream()
            disconnected.append(stream)
            return httpx.Response(200, stream=stream)
        return httpx.Response(200, json={"ok": True})

    instance = client(handler)
    try:
        assert await instance.get_schema() == {"ok": True}
        assert sum(item.method == "GET" for item in calls) == 2
        assert disconnected[0].closed
        calls.clear()
        result = await instance.create_model({"submission_key": "exact"})
        assert result["_status_code"] >= 400
        assert len(calls) == 1
        assert "reconcile" in result["_next_action"].lower()
        assert disconnected[1].closed
        assert instance._admission.active == 0
        assert await instance.get_schema() == {"ok": True}
        assert sum(item.method == "GET" for item in calls) == 1
    finally:
        await instance.close()


@pytest.mark.anyio
async def test_cooperative_cancel_at_parse_boundary_releases_permit_without_retry(monkeypatch):
    """Cancellation at an awaitable parse boundary releases admission and does not retry.

    The test replaces ``_parse_response`` with an await point. It does not interrupt
    synchronous ``json.loads``. Parsing runs inside the request deadline, but a
    synchronous parser is not itself cancellable, so a large body can overshoot that
    deadline until the next await. The deadline then returns ``request_deadline_exceeded``
    rather than cutting the parser mid-call.
    """
    entered = asyncio.Event()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    async def parsing(self, response, body=None):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(SimbaAPIClient, "_parse_response", parsing)
    instance = client(handler, total_seconds=10)
    task = asyncio.create_task(instance.get_schema())
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=1)
        assert len(calls) == 1
        assert instance._admission.active == 0
        assert not instance._admission.callers
    finally:
        await instance.close()


@pytest.mark.anyio
async def test_deadline_includes_queue_and_releases_waiter():
    admission = RequestAdmission(policy())
    caller = admission.identity("synthetic")
    entered = asyncio.Event()
    release = asyncio.Event()

    async def hold():
        async with admission.enter(caller):
            entered.set()
            await release.wait()

    holding = asyncio.create_task(hold())
    await entered.wait()
    try:
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.01), admission.enter(caller):
                pytest.fail("must remain queued")
        assert not admission.waiters
        assert admission.active == 1
    finally:
        release.set()
        await holding
    assert admission.active == 0
    assert not admission.callers


@pytest.mark.anyio
async def test_caller_queue_bound_does_not_block_other_caller():
    admission = RequestAdmission(policy(max_queued_per_caller=1))
    first, second = admission.identity("first"), admission.identity("second")
    entered = asyncio.Event()

    async def wait():
        async with admission.enter(first):
            entered.set()

    async with admission.enter(first):
        waiter = asyncio.create_task(wait())
        await asyncio.sleep(0)
        with pytest.raises(RequestOverload):
            async with admission.enter(first):
                pytest.fail("queue full")
        async with admission.enter(second):
            assert admission.active == 2
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert not entered.is_set()
    assert not admission.waiters and not admission.callers


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["http", "backoff"])
async def test_cancel_releases_permits_without_retry(phase, monkeypatch):
    entered = asyncio.Event()
    calls = []

    async def handler(request):
        calls.append(request)
        if phase == "http":
            entered.set()
            await asyncio.Event().wait()
        return httpx.Response(503, headers={"retry-after": "1"})

    async def sleeping(_):
        entered.set()
        await asyncio.Event().wait()

    if phase == "backoff":
        monkeypatch.setattr("simba_mcp.api_client.asyncio.sleep", sleeping)
    instance = client(handler, total_seconds=10)
    task = asyncio.create_task(instance.get_schema())
    await entered.wait()
    task.cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(calls) == 1
        assert instance._admission.active == 0
        assert not instance._admission.callers
    finally:
        await instance.close()


@pytest.mark.anyio
async def test_operation_deadline_and_timeout_phases():
    seen = []

    async def handler(request):
        seen.append(request)
        await asyncio.sleep(0.05)
        return httpx.Response(200, json={"ok": True})

    instance = client(handler, operation_seconds={"write": 0.01})
    try:
        result = await instance.create_model({"submission_key": "exact"})
        assert result["_status_code"] == 504
        assert "same study submission key" in result["_next_action"]
        assert all(value <= 0.01001 for value in seen[0].extensions["timeout"].values())
        assert instance._admission.active == 0
    finally:
        await instance.close()


def test_policy_configuration_and_opaque_identity():
    assert policy_from_json(None) is None
    assert policy_from_json("") is None
    assert policy_from_json("   ") is None
    assert policy_from_json("false") is None
    assert policy_from_json(json.dumps(policy().__dict__)) == policy()
    for invalid in (
        {"total_seconds": True},
        {"max_active": 0},
        {"max_queued": -1},
        {"operation_seconds": {"wrong": 1}},
    ):
        with pytest.raises(ValueError):
            policy(**invalid)
    admission = RequestAdmission(policy())
    assert admission.identity("secret") != b"secret"
    assert admission.identity("secret") == admission.identity("secret")
    assert admission.identity("rotated") != admission.identity("secret")


@pytest.mark.anyio
async def test_shared_client_queue_deadline_and_caller_context():
    entered = asyncio.Event()
    release = asyncio.Event()
    seen = []

    async def handler(request):
        seen.append(request.headers["authorization"])
        entered.set()
        await release.wait()
        return httpx.Response(200, json={"ok": True})

    instance = client(handler, max_active=1, total_seconds=0.03)

    async def run(key):
        token = CALLER_API_KEY.set(key)
        try:
            return await instance.get_schema()
        finally:
            CALLER_API_KEY.reset(token)

    holding = asyncio.create_task(run("caller-one"))
    await entered.wait()
    queued = asyncio.create_task(run("caller-two"))
    try:
        results = await asyncio.gather(holding, queued)
        assert all(r["_status_code"] == 504 for r in results)
        assert len(seen) <= 2
        assert set(seen) <= {"Bearer caller-one", "Bearer caller-two"}
        assert CALLER_API_KEY.get() is None
        assert not instance._admission.waiters and not instance._admission.callers
        assert instance._admission.active == 0
    finally:
        release.set()
        await instance.close()


@pytest.mark.anyio
async def test_stream_cancellation_closes_response_and_releases_admission():
    entered = asyncio.Event()

    class Stream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            entered.set()
            yield b'{"x":'
            await asyncio.Event().wait()

        async def aclose(self):
            self.closed = True

    stream = Stream()
    instance = client(
        lambda _: httpx.Response(200, stream=stream, headers={"content-type": "application/json"})
    )
    task = asyncio.create_task(instance.get_schema())
    await entered.wait()
    task.cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stream.closed
        assert instance._admission.active == 0
    finally:
        await instance.close()


@pytest.mark.anyio
async def test_fake_clock_retry_loop_cannot_reset_overall_budget(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(
        "simba_mcp.api_client.RequestBudget",
        lambda seconds: RequestBudget(seconds, clock=lambda: clock[0]),
    )
    monkeypatch.setattr("simba_mcp.api_client.random.uniform", lambda *_: 0.5)

    async def sleep(delay):
        clock[0] += delay

    monkeypatch.setattr("simba_mcp.api_client.asyncio.sleep", sleep)
    calls = []

    def handler(request):
        calls.append(request)
        clock[0] += 0.4
        return httpx.Response(503)

    instance = client(handler)
    try:
        result = await instance.get_schema()
        assert result["_status_code"] == 504
        assert len(calls) == 2
        assert clock[0] == 1.3
        assert instance._admission.active == 0
    finally:
        await instance.close()


@pytest.mark.anyio
async def test_full_ineligible_caller_queue_does_not_refuse_free_slot():
    admission = RequestAdmission(policy(max_queued=1, max_queued_per_caller=1))
    first, second = admission.identity("first"), admission.identity("second")

    async def queued():
        async with admission.enter(first):
            pass

    async with admission.enter(first):
        waiting = asyncio.create_task(queued())
        await asyncio.sleep(0)
        assert len(admission.waiters) == 1
        async with admission.enter(second):
            assert admission.active == 2
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
    assert admission.active == 0
    assert not admission.callers and not admission.waiters
