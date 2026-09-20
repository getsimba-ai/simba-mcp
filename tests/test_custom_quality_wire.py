"""Custom calculations remain data across the actual MCP transport."""

import json

import httpx
import pytest
from starlette.testclient import TestClient

from simba_mcp import runtime, server
from simba_mcp.api_client import SimbaAPIClient


@pytest.mark.parametrize(
    "operation",
    [
        "define",
        "submit",
        "legacy",
        "boolean",
        "manual_definition",
        "champion_read",
        "prediction",
        "protocol",
        "pair",
    ],
)
def test_custom_quality_wire(monkeypatch, operation):
    evidence = {
        "metric": "custom:benchmark",
        "value": 8,
        "method": "Manual ratio",
        "source_reference": "Synthetic export",
        "source_sha256": "b" * 64,
    }
    if operation == "pair":
        tool = "assess_study_validation_pair"
        arguments = {
            "study_id": "s",
            "full_run_id": "full",
            "validation_run_id": "holdout",
            "policy_id": "p",
        }
        expected = {k: v for k, v in arguments.items() if k != "study_id"}
    elif operation == "champion_read":
        tool = "get_study_champion"
        arguments = {"study_id": "s"}
        expected = None
    elif operation in ("define", "manual_definition", "prediction", "protocol"):
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
        if operation == "protocol":
            arguments["validation_protocol"] = {
                "kind": "temporal_holdout",
                "training_end": "2026-01-08",
                "prediction_start": "2026-01-15",
                "prediction_end": "2026-01-22",
                "min_draws": 1000,
                "min_tune": 1500,
                "min_chains": 2,
                "max_r_hat": 1.01,
                "max_prediction_wape": 0.15,
                "require_policy_review": True,
                "retained_sampling": {
                    "min_ess_bulk": 400,
                    "min_ess_tail": 300,
                    "max_divergences": 0,
                },
            }
        if operation == "prediction":
            arguments["checks"] = [{"metric": "prediction_wape", "maximum": 0.15, "required": True}]
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
        assert request.method == ("GET" if operation == "champion_read" else "POST")
        if operation == "champion_read":
            assert request.url.path == "/api/v1/studies/s/champion"
        else:
            assert json.loads(request.content) == expected
        return httpx.Response(
            201,
            json={
                "id": "saved",
                "status": "not_evaluated",
                **(
                    {
                        "sampling_evidence": [
                            {"role": "full", "record": {"divergences": 0}},
                            {"role": "validation", "record": None},
                        ]
                    }
                    if operation == "pair"
                    else {}
                ),
            },
        )

    async def get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://example.test", transport=httpx.MockTransport(handle)
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
    if operation == "pair":
        assert result["structuredContent"]["sampling_evidence"][0]["record"]["divergences"] == 0
        assert result["structuredContent"]["sampling_evidence"][1]["record"] is None
