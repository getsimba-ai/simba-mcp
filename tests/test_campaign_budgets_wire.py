"""Public synthetic campaign budget requests over the real MCP wire."""

import json
from urllib.parse import parse_qs

import anyio
import httpx
import pytest
from starlette.testclient import TestClient

from simba_mcp import runtime, server
from simba_mcp.api_client import SimbaAPIClient
from tests.hosted_backend import hosted_transport


def call(monkeypatch, tool, arguments, response, status=200):
    seen = []

    def handle(request):
        seen.append(
            {
                "method": request.method,
                "path": request.url.path,
                "query": parse_qs(request.url.query.decode()),
                "body": json.loads(request.content) if request.content else None,
            }
        )
        return httpx.Response(status, json=response)

    async def get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="http://test", transport=hosted_transport(handle)
            )
        return self._client

    monkeypatch.setattr(runtime, "_serving_http", runtime._serving_http)
    monkeypatch.setattr(SimbaAPIClient, "_get_client", get_client)
    with TestClient(runtime.create_app(server.create_server(profile="marketer"))) as client:
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
    return seen, result


def test_marginal_query_and_unavailable_evidence_are_preserved(monkeypatch):
    response = {
        "context_key": "synthetic",
        "currency": "GBP",
        "minor_digits": 2,
        "channels": [
            {
                "channel": "meta_activity",
                "status": "unavailable",
                "reason": "curve_basis_unavailable",
            }
        ],
        "rows": [],
        "provenance": {"map_version": 3},
    }
    seen, result = call(
        monkeypatch,
        "get_campaign_marginal_returns",
        {
            "model_hash": "synthetic-model",
            "start": "2026-09-01",
            "end": "2026-09-28",
            "level": "adset",
        },
        response,
    )
    assert result["structuredContent"] == response
    assert seen == [
        {
            "method": "GET",
            "path": "/api/v1/campaigns/marginal",
            "query": {
                "model": ["synthetic-model"],
                "start": ["2026-09-01"],
                "end": ["2026-09-28"],
                "level": ["adset"],
            },
            "body": None,
        }
    ]


@pytest.mark.parametrize(
    "source", [{"channel_daily_budgets": {"meta_activity": 1000.01}}, {"optimizer_run_id": 42}]
)
def test_calculation_forwards_exact_source_and_identity(monkeypatch, source):
    arguments = {
        "model_hash": "synthetic-model",
        "observation_window": {"start": "2026-09-01", "end": "2026-09-28"},
        "currency": "GBP",
        "max_step_fraction": 0.1,
        "expected_context_key": "a" * 64,
        "level": "adset",
        "bounds": [
            {
                "platform": "meta",
                "account_id": "a",
                "campaign_id": "c",
                "adset_id": "s",
                "min": 0,
                "max": 500.01,
            }
        ],
        **source,
    }
    response = {
        "channels": [
            {
                "channel": "meta_activity",
                "status": "unavailable",
                "reason": "bounds_infeasible",
                "feasible_range": [900, 1100],
            }
        ]
    }
    seen, result = call(monkeypatch, "recommend_campaign_budgets", arguments, response)
    assert result["structuredContent"] == response
    assert seen == [
        {
            "method": "POST",
            "path": "/api/v1/campaigns/daily-budgets",
            "query": {},
            "body": {
                "model": arguments["model_hash"],
                **{k: v for k, v in arguments.items() if k != "model_hash"},
            },
        }
    ]


def test_server_validation_is_not_silently_repaired(monkeypatch):
    arguments = {
        "model_hash": "synthetic-model",
        "observation_window": {},
        "currency": "GBP",
        "channel_daily_budgets": {},
        "optimizer_run_id": 42,
        "bounds": [],
    }
    seen, result = call(
        monkeypatch,
        "recommend_campaign_budgets",
        arguments,
        {"error": "Supply exactly one budget source", "code": "invalid_request"},
        400,
    )
    assert len(seen) == 1
    assert seen[0]["body"]["channel_daily_budgets"] == {}
    assert seen[0]["body"]["optimizer_run_id"] == 42
    assert result["isError"]


def test_ready_response_keeps_continuous_rounding_and_provenance(monkeypatch):
    response = {
        "channels": [
            {
                "channel": "meta_activity",
                "status": "ready",
                "total_daily_budget": 1000.01,
                "rows": [
                    {
                        "platform": "meta",
                        "account_id": "a",
                        "campaign_id": "c",
                        "adset_id": None,
                        "continuous_budget": 633.006,
                        "recommended_daily_budget": 633.01,
                        "miroas_hdi": None,
                        "interval_status": "unavailable",
                    }
                ],
                "explanation": "Inherited channel shape.",
                "assumptions": [],
            }
        ],
        "provenance": {"curve_revision": "synthetic-revision", "map_version": 3},
    }
    seen, result = call(
        monkeypatch,
        "recommend_campaign_budgets",
        {
            "model_hash": "synthetic-model",
            "observation_window": {"start": "2026-09-01", "end": "2026-09-28"},
            "currency": "GBP",
            "channel_daily_budgets": {"meta_activity": 1000.01},
        },
        response,
    )
    assert len(seen) == 1
    assert result["structuredContent"] == response
    assert seen[0]["body"]["max_step_fraction"] == 0.2
    assert seen[0]["body"]["level"] == "campaign"
    assert "bounds" not in seen[0]["body"]
    assert "optimizer_run_id" not in seen[0]["body"]


@pytest.mark.parametrize("profile", ["full", "marketer", "reviewer"])
def test_tools_are_read_only_in_all_relevant_profiles(profile):
    tools = {
        tool.name: tool for tool in anyio.run(server.create_server(profile=profile).list_tools)
    }
    for name in ("get_campaign_marginal_returns", "recommend_campaign_budgets"):
        assert tools[name].annotations.read_only_hint is True
        assert tools[name].annotations.destructive_hint is False
        assert tools[name].annotations.idempotent_hint is True
