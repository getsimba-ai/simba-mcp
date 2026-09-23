"""Refused backend calls are tool execution errors on the wire (jellyfish #824).

Tests the real HTTP transport, not direct Python returns: `isError` must be true whenever the
structured payload carries `_status_code >= 400`, the structured payload must be unchanged,
and a backend `code` must become `_error_code` with a code-specific `_next_action`.
"""

import json

import httpx
import pytest
from starlette.testclient import TestClient

from simba_mcp import runtime, server
from simba_mcp.api_client import SimbaAPIClient


def _call(client, tool, arguments, key="synthetic-test-key"):
    headers = {"Accept": "application/json, text/event-stream"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return client.post(
        "/",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
    ).json()["result"]


@pytest.mark.parametrize("scenario", ["refused_with_code", "refused_legacy", "ok"])
def test_refusals_set_is_error_and_keep_the_payload(monkeypatch, scenario):
    def handle(request):
        assert request.url.path == "/api/v1/studies/s/quality-policies/p"
        if scenario == "refused_with_code":
            return httpx.Response(
                409,
                json={
                    "error": "This policy is retired; choose an active policy",
                    "code": "policy_retired",
                },
            )
        if scenario == "refused_legacy":
            return httpx.Response(409, json={"error": "Study is not active"})
        return httpx.Response(200, json={"id": "p", "retired_at": None})

    async def get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://example.test", transport=httpx.MockTransport(handle)
            )
        return self._client

    monkeypatch.setattr(runtime, "_serving_http", runtime._serving_http)
    monkeypatch.setattr(SimbaAPIClient, "_get_client", get_client)
    with TestClient(server._create_app()) as client:
        result = _call(client, "retire_quality_policy", {"study_id": "s", "policy_id": "p"})

    content = result["structuredContent"]
    if scenario == "ok":
        assert not result.get("isError", False)
        assert content == {"id": "p", "retired_at": None}
        return
    assert result["isError"] is True
    assert content["_status_code"] == 409
    # The text block carries the same JSON for clients that do not read structuredContent.
    assert json.loads(result["content"][0]["text"]) == content
    if scenario == "refused_with_code":
        assert content["_error_code"] == "policy_retired"
        assert content["code"] == "policy_retired"
        assert "retired_at is null" in content["_next_action"]
        assert content["error"] == "This policy is retired; choose an active policy"
    else:
        # Older backends without `code`: the status-derived guess is kept unchanged.
        assert content["_error_code"] == "conflict"
        assert content["error"] == "Study is not active"


def test_keyless_call_is_an_error_on_the_wire(monkeypatch):
    monkeypatch.setattr(runtime, "_serving_http", runtime._serving_http)
    with TestClient(server._create_app()) as client:
        result = _call(client, "list_studies", {"project_id": 1}, key="")
    assert result["isError"] is True
    content = result["structuredContent"]
    assert content["_status_code"] == 401
    assert content["_error_code"] == "authentication_required"
