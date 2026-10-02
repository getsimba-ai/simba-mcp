"""retire_quality_policy reaches the backend as PATCH {"retired": bool} and surfaces refusals."""

import json

import httpx
import pytest
from starlette.testclient import TestClient

from simba_mcp import runtime, server
from simba_mcp.api_client import SimbaAPIClient


@pytest.mark.parametrize("operation", ["retire", "restore", "refused"])
def test_policy_lifecycle_wire(monkeypatch, operation):
    retired = operation != "restore"
    row = {
        "id": "p",
        "specification": {"name": "Weekly policy"},
        "retired_at": "2026-09-23T10:00:00" if retired else None,
        "usage": {
            "runs_launched": 2,
            "evaluations": 1,
            "resolutions": 0,
            "champion_acceptances": 0,
        },
    }

    def handle(request):
        assert request.method == "PATCH"
        assert request.url.path == "/api/v1/studies/s/quality-policies/p"
        assert json.loads(request.content) == {"retired": retired}
        if operation == "refused":
            return httpx.Response(404, json={"error": "Policy not found in this study"})
        return httpx.Response(200, json=row)

    async def get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://example.test", transport=httpx.MockTransport(handle)
            )
        return self._client

    # _create_app flips the runtime into HTTP mode; restore it so later tests see stdio defaults.
    monkeypatch.setattr(runtime, "_serving_http", runtime._serving_http)
    monkeypatch.setattr(SimbaAPIClient, "_get_client", get_client)
    arguments = {"study_id": "s", "policy_id": "p"}
    if not retired:
        arguments["retired"] = False
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
                "params": {"name": "retire_quality_policy", "arguments": arguments},
            },
        ).json()["result"]
    content = result["structuredContent"]
    if operation == "refused":
        assert content["_status_code"] == 404 and content["_error_code"] == "not_found"
    else:
        assert not result.get("isError", False)
        assert content["retired_at"] == row["retired_at"]
        assert content["usage"]["runs_launched"] == 2
