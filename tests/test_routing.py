"""Advisory routing boundaries under the real SDK and shared caller context."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from simba_mcp import runtime, user_profiles
from simba_mcp.api_client import SimbaAPIClient
from simba_mcp.guidance import MANIFEST
from simba_mcp.guidance.routing import (
    CHOICES,
    WORKFLOWS,
    RoutingResult,
    recommendation,
    validate_request,
)
from simba_mcp.metadata import annotations_for
from simba_mcp.profiles import PROFILES
from simba_mcp.server import TOOLS, create_server
from simba_mcp.tools.routing import recommend_workflow
from simba_mcp.user_profiles import CURRENT_PROFILE


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_map_uses_canonical_topics_and_registered_tools():
    known = {tool.__name__ for tool in TOOLS}
    assert set(WORKFLOWS) == set(MANIFEST["topics"])
    assert len(CHOICES) == 10
    for _, tools in WORKFLOWS.values():
        assert set(tools) <= known
        assert len(tools) == len(set(tools))
    assert all("recommend_workflow" in names for names in PROFILES.values())
    effects = annotations_for("recommend_workflow")
    assert effects.read_only_hint and not effects.idempotent_hint and effects.open_world_hint


@pytest.mark.parametrize("text", ["", "  ", None, 2, "a" * 4001, "🙂" * 1001])
def test_invalid_request_boundaries(text):
    with pytest.raises(ValueError):
        validate_request(text)


@pytest.mark.parametrize(
    "changes",
    [
        {"workflow": "execute_anything"},
        {"confidence": float("nan")},
        {"confidence": True},
        {"schema_version": True},
        {"commands": ["create_model"]},
        {"outcome": "fallback"},
        {"workflow": "unsupported"},
    ],
)
def test_malformed_classification_is_never_accepted(changes):
    with pytest.raises(ValidationError):
        RoutingResult.model_validate(
            {"outcome": "recommended", "workflow": "mmm", "confidence": 0.95, **changes}
        )


def test_filtered_tools_do_not_leak_excluded_names():
    result = recommendation(
        {"outcome": "recommended", "workflow": "mmm", "confidence": 0.95}, PROFILES["reviewer"]
    )
    assert result["profile_limited"] and "create_model" not in str(result)
    assert result["advisory_only"]


@pytest.mark.anyio
async def test_wrapper_no_retry_and_current_profile_restriction():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200, json={"outcome": "recommended", "workflow": "mmm", "confidence": 0.95}
        )

    client = SimbaAPIClient("https://example.invalid", "synthetic")
    client._client = httpx.AsyncClient(
        base_url=client.base_url, transport=httpx.MockTransport(handler)
    )
    app = runtime.AppContext(
        client=client, serving_http=False, tool_names=tuple(tool.__name__ for tool in TOOLS)
    )
    ctx = SimpleNamespace(request_context=SimpleNamespace(lifespan_context=app))
    token = CURRENT_PROFILE.set("reviewer")
    try:
        result = await recommend_workflow("Build a model", ctx)
        assert len(requests) == 1 and requests[0].method == "POST"
        assert "create_model" not in result["suggested_tools"]
        assert result["profile_limited"]
    finally:
        CURRENT_PROFILE.reset(token)
        await client.close()


@pytest.mark.anyio
async def test_malformed_backend_and_invalid_input_do_not_execute_tools():
    client = SimpleNamespace(workflow_request=AsyncMock(return_value={"execute": "create_model"}))
    app = runtime.AppContext(client=client, serving_http=False)
    ctx = SimpleNamespace(request_context=SimpleNamespace(lifespan_context=app))
    result = await recommend_workflow("Explain ROI", ctx)
    assert result["outcome"] == "fallback" and result["reason"] == "invalid_answer"
    result = await recommend_workflow("", ctx)
    assert result["_status_code"] == 400
    assert client.workflow_request.await_count == 1


@pytest.mark.parametrize("profile", ["full", "reviewer", "marketer"])
def test_real_http_sdk_preserves_profile_and_isolation(profile, monkeypatch):
    user_profiles._cache.clear()
    received = []

    def handler(request):
        received.append(request)
        if request.url.path.endswith("preferences"):
            return httpx.Response(200, json={"schema_version": 1, "profile": profile})
        return httpx.Response(
            200, json={"outcome": "recommended", "workflow": "mmm", "confidence": 0.95}
        )

    async def mocked(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, transport=httpx.MockTransport(handler)
            )
        return self._client

    monkeypatch.setattr(SimbaAPIClient, "_get_client", mocked)
    app = runtime.create_app(create_server())
    headers = {
        "Authorization": "Bearer synthetic-routing",
        "Accept": "application/json, text/event-stream",
    }
    with TestClient(app) as browser:
        response = browser.post(
            "/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "recommend_workflow", "arguments": {"request": "Build a model"}},
            },
        )
    result = response.json()["result"]["structuredContent"]
    assert result["advisory_only"]
    assert ("create_model" in result["suggested_tools"]) == (profile == "full")
    assert all(r.headers["authorization"] == "Bearer synthetic-routing" for r in received)
    assert CURRENT_PROFILE.get() == "full"
    user_profiles._cache.clear()
