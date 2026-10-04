"""Hosted account profiles through real SDK dispatch and isolated caller state."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from mcp.types import ListToolsResult, Tool
from starlette.testclient import TestClient

from simba_mcp import runtime, user_profiles
from simba_mcp.api_client import CALLER_API_KEY, SimbaAPIClient
from simba_mcp.profiles import PROFILES
from simba_mcp.server import create_server
from simba_mcp.user_profiles import UserProfileMiddleware


@pytest.fixture(autouse=True)
def empty_cache():
    user_profiles._cache.clear()
    user_profiles._next_warning = 0.0
    yield
    user_profiles._cache.clear()


@pytest.fixture
def anyio_backend():
    return "asyncio"


def context(client, *, method="tools/list", params=None, bearer="synthetic-reviewer", http=True):
    return SimpleNamespace(
        method=method,
        params=params,
        request=SimpleNamespace(headers={"aUtHoRiZaTiOn": f"bEaReR {bearer}"} if bearer else {}),
        lifespan_context=runtime.AppContext(client=client, serving_http=http),
    )


def api_client():
    return SimpleNamespace(
        base_url="https://example.invalid",
        _request=AsyncMock(return_value={"schema_version": 1, "profile": "reviewer"}),
    )


@pytest.mark.anyio
@pytest.mark.parametrize("as_dict", [False, True])
async def test_filter_keeps_shape_and_does_not_mutate_original(as_dict):
    client = api_client()
    tools = [Tool(name=n, input_schema={"type": "object"}) for n in ("list_models", "create_model")]
    original = ListToolsResult(tools=tools, next_cursor="next")
    if as_dict:
        original = original.model_dump(by_alias=True)
    next_call = AsyncMock(return_value=original)
    result = await UserProfileMiddleware()(context(client), next_call)
    assert CALLER_API_KEY.get() is None
    if as_dict:
        assert [t["name"] for t in result["tools"]] == ["list_models"]
        assert result["nextCursor"] == "next"
        assert len(original["tools"]) == 2
    else:
        assert [t.name for t in result.tools] == ["list_models"]
        assert result.next_cursor == "next"
        assert len(original.tools) == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    "method,bearer,http",
    [("initialize", "x", True), ("tools/list", "", True), ("tools/list", "x", False)],
)
async def test_non_hosted_or_uncredentialed_messages_make_no_lookup(method, bearer, http):
    client = api_client()
    next_call = AsyncMock(return_value={"untouched": True})
    assert await UserProfileMiddleware()(
        context(client, method=method, bearer=bearer, http=http), next_call
    ) == {"untouched": True}
    client._request.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        {"_status_code": 503},
        {"_status_code": 404},
        {"_status_code": 401},
        {"profile": "reviewer"},
        {"schema_version": 2, "profile": "reviewer"},
        {"schema_version": 1, "profile": []},
        {"schema_version": True, "profile": "reviewer"},
        {"schema_version": 1, "profile": "unknown"},
    ],
)
async def test_failures_and_invalid_contracts_pass_through_without_caching(response):
    client = api_client()
    client._request.return_value = response
    original = {"tools": [{"name": "create_model"}]}
    for _ in range(2):
        assert (
            await UserProfileMiddleware()(context(client), AsyncMock(return_value=original))
            is original
        )
    assert client._request.await_count == 2
    assert not user_profiles._cache
    assert CALLER_API_KEY.get() is None


@pytest.mark.anyio
async def test_unexpected_lookup_error_falls_back_without_logging_credentials(caplog):
    client = api_client()
    client._request.side_effect = RuntimeError("synthetic-reviewer private payload")
    original = {"tools": [{"name": "create_model"}]}
    for _ in range(2):
        assert (
            await UserProfileMiddleware()(context(client), AsyncMock(return_value=original))
            is original
        )
    assert client._request.await_count == 2
    assert not user_profiles._cache
    assert CALLER_API_KEY.get() is None
    assert "synthetic-reviewer" not in caplog.text and "private payload" not in caplog.text


@pytest.mark.anyio
async def test_outer_timeout_and_cancellation_restore_prior_credentials(monkeypatch):
    client = api_client()

    async def slow(*args, **kwargs):
        assert CALLER_API_KEY.get() == "synthetic-reviewer"
        await asyncio.sleep(100)

    client._request.side_effect = slow
    monkeypatch.setattr(user_profiles, "LOOKUP_SECONDS", 0.01)
    old = CALLER_API_KEY.set("outer-synthetic")
    try:
        original = {"tools": [{"name": "create_model"}]}
        assert (
            await UserProfileMiddleware()(context(client), AsyncMock(return_value=original))
            is original
        )
        assert CALLER_API_KEY.get() == "outer-synthetic"
        client._request.side_effect = asyncio.CancelledError
        with pytest.raises(asyncio.CancelledError):
            await UserProfileMiddleware()(context(client), AsyncMock())
        assert CALLER_API_KEY.get() == "outer-synthetic"
    finally:
        CALLER_API_KEY.reset(old)


@pytest.mark.anyio
async def test_cache_expiry_caller_and_backend_isolation(monkeypatch):
    now = 100.0
    monkeypatch.setattr(user_profiles.time, "monotonic", lambda: now)
    client = api_client()
    original = {"tools": [{"name": "list_models"}, {"name": "create_model"}]}
    middleware = UserProfileMiddleware()
    for _ in range(2):
        await middleware(context(client), AsyncMock(return_value=original))
    assert client._request.await_count == 1
    await middleware(context(client, bearer="other-caller"), AsyncMock(return_value=original))
    assert client._request.await_count == 2
    client.base_url = "https://other.invalid"
    await middleware(context(client), AsyncMock(return_value=original))
    assert client._request.await_count == 3
    now += 30
    await middleware(context(client), AsyncMock(return_value=original))
    assert client._request.await_count == 4
    assert all("synthetic-reviewer" not in key for key in user_profiles._cache)


def test_cache_is_bounded_and_warnings_are_redacted_and_limited(monkeypatch, caplog):
    monkeypatch.setattr(user_profiles, "MAX_CACHE_ENTRIES", 2)
    for key in range(3):
        user_profiles._remember(("backend", str(key)), "full")
    assert len(user_profiles._cache) == 2
    assert ("backend", "0") not in user_profiles._cache
    user_profiles._warn_fallback()
    user_profiles._warn_fallback()
    assert len(caplog.records) == 1
    assert "operator's tool catalogue" in caplog.text


def wire(client, method, bearer=None, params=None):
    headers = {"Accept": "application/json, text/event-stream"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    response = client.post(
        "/",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
    )
    assert response.status_code == 200, response.text
    return response.json()["result"]


def test_real_hosted_concurrent_callers_refusal_and_cache(monkeypatch):
    exchanges = []

    async def backend(request):
        bearer = request.headers["authorization"]
        exchanges.append((request.url.path, bearer))
        await asyncio.sleep(0)
        if request.url.path == "/api/v1/mcp/preferences":
            return httpx.Response(
                200,
                json={
                    "schema_version": 1,
                    "profile": "reviewer" if bearer.endswith("reviewer") else "full",
                },
            )
        return httpx.Response(200, json={"caller": bearer})

    original = SimbaAPIClient._get_client

    async def mocked(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, transport=httpx.MockTransport(backend)
            )
        return await original(self)

    monkeypatch.setattr(SimbaAPIClient, "_get_client", mocked)
    with TestClient(runtime.create_app(create_server())) as client:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(wire, client, "tools/list", bearer)
                for bearer in ("synthetic-reviewer", "synthetic-full")
            ]
            reviewer, full = [future.result() for future in futures]
        assert {t["name"] for t in reviewer["tools"]} == PROFILES["reviewer"]
        assert len(reviewer["tools"]) == 50 and len(full["tools"]) == 94
        excluded = wire(
            client, "tools/call", "synthetic-reviewer", {"name": "create_model", "arguments": {}}
        )
        assert excluded["isError"] is True
        assert excluded["structuredContent"]["code"] == "profile_excluded"
        assert excluded["structuredContent"]["_error_code"] == "profile_excluded"
        assert excluded["structuredContent"]["_status_code"] == 403
        assert "Profile > Connected apps" in excluded["structuredContent"]["_next_action"]
        assert len(exchanges) == 2  # lookup only, no tool dispatch
        for bearer in ("synthetic-reviewer", "synthetic-full"):
            result = wire(client, "tools/call", bearer, {"name": "list_models", "arguments": {}})
            assert result["structuredContent"]["caller"] == f"Bearer {bearer}"
        assert CALLER_API_KEY.get() is None
        assert len([p for p, _ in exchanges if p == "/api/v1/mcp/preferences"]) == 2


@pytest.mark.parametrize(
    "status,profile", [(404, "full"), (503, "full"), (401, "full"), (200, "marketer")]
)
def test_real_hosted_fallback_or_operator_upper_bound(monkeypatch, status, profile):
    async def backend(request):
        if request.url.path == "/api/v1/mcp/preferences":
            return httpx.Response(status, json={"schema_version": 1, "profile": "full"})
        return httpx.Response(401, json={"error": "Synthetic credential refused"})

    async def mocked(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, transport=httpx.MockTransport(backend)
            )
        return self._client

    monkeypatch.setattr(SimbaAPIClient, "_get_client", mocked)
    with TestClient(runtime.create_app(create_server(profile=profile))) as client:
        result = wire(client, "tools/list", "synthetic")
        names = {t["name"] for t in result["tools"]}
        assert len(names) == (54 if profile == "marketer" else 94)
        no_bearer = wire(client, "tools/list")
        assert len(no_bearer["tools"]) == len(names)
        refusal = wire(client, "tools/call", "synthetic", {"name": "list_models", "arguments": {}})
        assert refusal["isError"] and refusal["structuredContent"]["_status_code"] == 401
