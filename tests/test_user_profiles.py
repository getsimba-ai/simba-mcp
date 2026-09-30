"""Caller preferences only narrow response-local catalogues and tool dispatch."""

import asyncio
from types import SimpleNamespace

import pytest
from mcp.shared.exceptions import MCPError
from mcp.types import ListToolsResult, Tool

from simba_mcp.api_client import CALLER_API_KEY
from simba_mcp.user_profiles import UserProfileMiddleware


@pytest.fixture
def anyio_backend():
    return "asyncio"


def context(client, credential="one", method="tools/list", name=None):
    return SimpleNamespace(
        method=method,
        params={"name": name},
        request=SimpleNamespace(headers={"Authorization": f"Bearer {credential}"}),
        lifespan_context=SimpleNamespace(serving_http=True, client=client),
    )


class Client:
    def __init__(self, values):
        self.values = values
        self.calls = []

    async def _request(self, method, path, **kwargs):
        assert kwargs == {"retry_safe": False}
        key = CALLER_API_KEY.get()
        self.calls.append((method, path, key))
        await asyncio.sleep(0)
        assert CALLER_API_KEY.get() == key
        return self.values[key]


@pytest.mark.anyio
async def test_concurrent_profiles_do_not_mutate_shared_tools_or_credentials():
    original = ListToolsResult(
        tools=[
            Tool(name="get_model_results", inputSchema={"type": "object"}),
            Tool(name="create_model", inputSchema={"type": "object"}),
        ]
    )
    client = Client(
        {
            "one": {"schema_version": 1, "profile": "reviewer"},
            "two": {"schema_version": 1, "profile": "full"},
        }
    )

    async def next_handler(ctx):
        return original

    middleware = UserProfileMiddleware()
    first, second = await asyncio.gather(
        middleware(context(client), next_handler),
        middleware(context(client, "two"), next_handler),
    )
    assert [t.name for t in first.tools] == ["get_model_results"]
    assert len(second.tools) == len(original.tools) == 2
    assert CALLER_API_KEY.get() is None


@pytest.mark.anyio
async def test_profile_change_applies_without_replaying_a_write():
    client = Client({"one": {"schema_version": 1, "profile": "reviewer"}})
    calls = []

    async def next_handler(ctx):
        calls.append(ctx.params["name"])
        return {}

    middleware = UserProfileMiddleware()
    with pytest.raises(MCPError, match="outside your selected profile"):
        await middleware(context(client, method="tools/call", name="create_model"), next_handler)
    assert calls == []
    client.values["one"]["profile"] = "full"
    await middleware(context(client, method="tools/call", name="create_model"), next_handler)
    assert calls == ["create_model"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "value",
    [
        {"_status_code": 404},
        {"_status_code": 401},
        {"_status_code": 503},
        {"schema_version": 1, "profile": "invalid"},
        {},
    ],
)
async def test_lookup_failure_does_not_widen_or_dispatch(value):
    client = Client({"one": value})

    async def next_handler(ctx):
        pytest.fail("lookup failure must not dispatch")

    with pytest.raises(MCPError):
        await UserProfileMiddleware()(context(client), next_handler)
    assert CALLER_API_KEY.get() is None


@pytest.mark.anyio
async def test_stdio_keeps_operator_view_without_preference_lookup():
    client = Client({})

    async def next_handler(ctx):
        return "operator-view"

    ctx = context(client)
    ctx.lifespan_context.serving_http = False
    assert await UserProfileMiddleware()(ctx, next_handler) == "operator-view"
    assert client.calls == []


def test_real_http_middleware_concurrent_profiles_and_dispatch(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    from starlette.testclient import TestClient

    from simba_mcp import runtime
    from simba_mcp.api_client import SimbaAPIClient
    from simba_mcp.server import create_server

    seen = []
    preferences = {"one": "reviewer", "two": "full"}

    async def backend(self, method, path, **kwargs):
        caller = CALLER_API_KEY.get()
        await asyncio.sleep(0.01)
        assert CALLER_API_KEY.get() == caller
        seen.append((caller, method, path))
        if path == "/api/v1/mcp/preferences":
            assert kwargs.get("retry_safe") is False
            return {"schema_version": 1, "profile": preferences[caller]}
        return {"caller": caller}

    monkeypatch.setattr(SimbaAPIClient, "_request", backend)
    server = create_server("compact", profile="full")
    with TestClient(runtime.create_app(server)) as client:

        def request(caller, method="tools/list", params=None):
            return client.post(
                "/",
                headers={
                    "Authorization": f"Bearer {caller}",
                    "Accept": "application/json, text/event-stream",
                },
                json={"jsonrpc": "2.0", "id": caller, "method": method, "params": params or {}},
            ).json()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(request, ["one", "two"]))
        names = lambda result: {t["name"] for t in result["result"]["tools"]}
        assert "create_model" not in names(first)
        assert "create_model" in names(second)
        refused = request("one", "tools/call", {"name": "create_model", "arguments": {}})
        assert "outside your selected profile" in str(refused)
        assert all(path == "/api/v1/mcp/preferences" for _, _, path in seen)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda caller: request(
                        caller, "tools/call", {"name": "list_models", "arguments": {}}
                    ),
                    ["one", "two"],
                )
            )
        assert [x["result"]["structuredContent"]["caller"] for x in results] == ["one", "two"]
        preferences["one"] = "full"
        assert "create_model" in names(request("one"))
        assert "create_model" in names(request("two"))
    assert CALLER_API_KEY.get() is None


@pytest.mark.anyio
async def test_lookup_deadline_fails_closed_and_restores_credential(monkeypatch):
    import simba_mcp.user_profiles as module

    class SlowClient:
        async def _request(self, *args, **kwargs):
            await asyncio.sleep(1)

    async def forbidden(ctx):
        pytest.fail("Timed-out lookup must not dispatch")

    monkeypatch.setattr(module, "PREFERENCE_LOOKUP_SECONDS", 0.01)
    with pytest.raises(MCPError, match="Unable to resolve"):
        await UserProfileMiddleware()(context(SlowClient()), forbidden)
    assert CALLER_API_KEY.get() is None


@pytest.mark.parametrize(
    "value",
    [{"_status_code": 404}, {"_status_code": 503}, {"schema_version": True, "profile": "full"}],
)
def test_real_http_lookup_failures_and_missing_auth_fail_closed(monkeypatch, value):
    from starlette.testclient import TestClient

    from simba_mcp import runtime
    from simba_mcp.api_client import SimbaAPIClient
    from simba_mcp.server import create_server

    calls = []

    async def backend(self, method, path, **kwargs):
        calls.append(path)
        assert path == "/api/v1/mcp/preferences"
        return value

    monkeypatch.setattr(SimbaAPIClient, "_request", backend)
    with TestClient(runtime.create_app(create_server())) as client:
        for method, params in [
            ("tools/list", {}),
            ("tools/call", {"name": "list_models", "arguments": {}}),
        ]:
            result = client.post(
                "/",
                headers={
                    "Authorization": "Bearer synthetic",
                    "Accept": "application/json, text/event-stream",
                },
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            ).json()
            assert "Unable to resolve tool preferences" in result["error"]["message"]
        count = len(calls)
        result = client.post(
            "/",
            headers={"Accept": "application/json, text/event-stream"},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ).json()
        assert "Authentication required" in result["error"]["message"]
        assert len(calls) == count
