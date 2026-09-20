"""Custom calculations remain data across the actual MCP transport."""

import json

import httpx
import pytest
from starlette.testclient import TestClient

from simba_mcp import runtime, server
from simba_mcp.api_client import SimbaAPIClient


@pytest.mark.parametrize(
    "operation", ["define", "submit", "legacy", "boolean", "manual_definition"]
)
def test_custom_quality_wire(monkeypatch, operation):
    evidence = {
        "metric": "custom:benchmark",
        "value": 8,
        "method": "Manual ratio",
        "source_reference": "Synthetic export",
        "source_sha256": "b" * 64,
    }
    if operation in ("define", "manual_definition"):
        tool = "create_quality_policy"
        arguments = {
            "study_id": "s",
            "name": "Custom",
            "rationale": "Declared rule",
            "checks": [
                {
                    "metric": "custom:benchmark",
                    "name": "Benchmark",
                    "units": "%",
                    "operator": "between",
                    "minimum": -10,
                    "maximum": 10,
                    "required": True,
                }
            ],
        }
        if operation == "manual_definition":
            arguments["checks"] = [
                {
                    "metric": "custom:review",
                    "name": "Review",
                    "kind": "manual",
                    "operator": "equals",
                    "expected": True,
                }
            ]
        expected = {key: value for key, value in arguments.items() if key != "study_id"}
    else:
        tool = "evaluate_study_run"
        arguments = {"run_id": "r", "policy_id": "p"}
        if operation in ("submit", "boolean"):
            if operation == "boolean":
                evidence["value"] = False
            arguments.update(expected_basis_hash="a" * 64, external_evidence=[evidence])
        expected = {key: value for key, value in arguments.items() if key != "run_id"}

    def handle(request):
        assert request.method == "POST"
        assert json.loads(request.content) == expected
        return httpx.Response(201, json={"id": "saved", "status": "not_evaluated"})

    async def get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://example.test/api/v1", transport=httpx.MockTransport(handle)
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
                "params": {"name": tool, "arguments": arguments},
            },
        ).json()["result"]
    assert not result.get("isError", False)
    assert result["structuredContent"]["id"] == "saved"
