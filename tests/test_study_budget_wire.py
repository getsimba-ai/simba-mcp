"""Additive study responses must survive the actual MCP wire protocol."""

import json

import httpx
import pytest
from starlette.testclient import TestClient

from simba_mcp import runtime, server
from simba_mcp.api_client import SimbaAPIClient


@pytest.mark.parametrize("with_budget", [False, True])
def test_list_runs_preserves_budget_and_older_backend_responses(monkeypatch, with_budget):
    response = {"runs": [{"id": "run-a", "state": "failed"}]}
    if with_budget:
        response["budget"] = {
            "attempts_used": 1,
            "attempts_remaining": 0,
            "active_runs": 0,
            "available_slots": 1,
            "can_reserve_attempt": False,
            "blockers": [
                {"code": "attempts_exhausted", "message": "Study attempt budget exhausted"}
            ],
            "future_capacity_detail": {"preserved": True},
        }

    def handle(request):
        assert request.method == "GET"
        assert request.url.path.endswith("/studies/study-a/runs")
        return httpx.Response(200, json=response)

    async def get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="http://test", transport=httpx.MockTransport(handle)
            )
        return self._client

    monkeypatch.setattr(runtime, "_serving_http", runtime._serving_http)
    monkeypatch.setattr(SimbaAPIClient, "_get_client", get_client)
    with TestClient(server._create_app()) as client:
        result = client.post(
            "/",
            headers={
                "Accept": "application/json, text/event-stream",
                "Authorization": "Bearer synthetic-test-key",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "list_study_runs", "arguments": {"study_id": "study-a"}},
            },
        ).json()["result"]
    assert not result.get("isError", False)
    assert result["structuredContent"] == response
    assert json.loads(result["content"][0]["text"]) == response
