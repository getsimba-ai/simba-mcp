"""Data reporting over the real MCP wire: get_data_report, upload roles and the results window."""

import json

import httpx
import pytest
from starlette.testclient import TestClient

from simba_mcp import runtime, server
from simba_mcp.api_client import SimbaAPIClient

REPORT = {
    "dataset": {
        "id": 7,
        "name": "panel.csv",
        "source": "upload",
        "version": None,
        "sha256": "a" * 64,
        "data_through": "2024-02-05",
    },
    "granularity": "month",
    "rows": [
        {
            "period_start": "2024-01-01",
            "period_end": "2024-01-31",
            "group": "tv",
            "metric": "spend",
            "value": 40.0,
            "unit": "currency",
        }
    ],
    "meta": {
        "basis": "dataset",
        "aggregation": {"spend": "sum"},
        "roles": {"tv_spend": "spend"},
        "channels": {},
    },
}


def _call(monkeypatch, handle, tool, arguments):
    async def get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="http://test", transport=httpx.MockTransport(handle)
            )
        return self._client

    monkeypatch.setattr(runtime, "_serving_http", runtime._serving_http)
    monkeypatch.setattr(SimbaAPIClient, "_get_client", get_client)
    profile = "data_scientist" if tool == "upload_data" else "reviewer"
    with TestClient(runtime.create_app(server.create_server(profile=profile))) as client:
        return client.post(
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


def test_get_data_report_passes_every_parameter(monkeypatch):
    seen = {}

    def handle(request):
        if request.url.path == "/api/v1/mcp/preferences":
            assert request.headers.get("authorization", "").startswith("Bearer ")
            return httpx.Response(200, json={"schema_version": 1, "profile": "full"})
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=REPORT)

    result = _call(
        monkeypatch,
        handle,
        "get_data_report",
        {
            "dataset_id": 7,
            "start": "2024-01-01",
            "end": "2024-03-31",
            "granularity": "month",
            "group_by": "channel",
            "hierarchy": "North",
            "metrics": ["kpi", "spend"],
            "roles": {"revenue": "kpi", "tv_grps": {"role": "media:grps", "channel": "tv"}},
        },
    )
    assert not result.get("isError", False)
    assert result["structuredContent"] == REPORT
    assert seen["path"].endswith("/api/v1/datasets/7/report")
    params = seen["params"]
    assert {
        k: params[k] for k in ("start", "end", "granularity", "group_by", "hierarchy", "metrics")
    } == {
        "start": "2024-01-01",
        "end": "2024-03-31",
        "granularity": "month",
        "group_by": "channel",
        "hierarchy": "North",
        "metrics": "kpi,spend",
    }
    assert json.loads(params["roles"])["tv_grps"] == {"role": "media:grps", "channel": "tv"}


def test_get_data_report_defaults_send_only_granularity(monkeypatch):
    seen = {}

    def handle(request):
        if request.url.path == "/api/v1/mcp/preferences":
            assert request.headers.get("authorization", "").startswith("Bearer ")
            return httpx.Response(200, json={"schema_version": 1, "profile": "full"})
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=REPORT)

    _call(monkeypatch, handle, "get_data_report", {"dataset_id": 7})
    assert seen["params"] == {"granularity": "native"}


def test_get_data_report_errors_keep_the_backend_code(monkeypatch):
    def handle(request):
        if request.url.path == "/api/v1/mcp/preferences":
            assert request.headers.get("authorization", "").startswith("Bearer ")
            return httpx.Response(200, json={"schema_version": 1, "profile": "full"})
        return httpx.Response(413, json={"error": "too many rows", "code": "report_too_large"})

    result = _call(monkeypatch, handle, "get_data_report", {"dataset_id": 7})
    assert result["isError"] is True
    body = result["structuredContent"]
    assert body["_status_code"] == 413 and body["code"] == "report_too_large"


def test_upload_roles_travel_as_json(monkeypatch):
    seen = {}

    def handle(request):
        if request.url.path == "/api/v1/mcp/preferences":
            assert request.headers.get("authorization", "").startswith("Bearer ")
            return httpx.Response(200, json={"schema_version": 1, "profile": "full"})
        seen["params"] = dict(request.url.params)
        return httpx.Response(201, json={"id": 9})

    _call(
        monkeypatch,
        handle,
        "upload_data",
        {"csv_content": "date,revenue\n2024-01-01,1\n", "roles": {"revenue": "kpi"}},
    )
    assert json.loads(seen["params"]["roles"]) == {"revenue": "kpi"}


@pytest.mark.parametrize(
    "window,expected",
    [
        ({}, {}),
        (
            {"start": "2024-01-01", "end": "2024-03-31", "granularity": "quarter"},
            {"start": "2024-01-01", "end": "2024-03-31", "granularity": "quarter"},
        ),
    ],
)
def test_model_results_window_parameters(monkeypatch, window, expected):
    seen = {}

    def handle(request):
        if request.url.path == "/api/v1/mcp/preferences":
            assert request.headers.get("authorization", "").startswith("Bearer ")
            return httpx.Response(200, json={"schema_version": 1, "profile": "full"})
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200, json={"model_hash": "m1", "results": {}, "meta": {"window": expected}}
        )

    _call(
        monkeypatch,
        handle,
        "get_model_results",
        {"model_hash": "m1", "sections": "channel_summary", **window},
    )
    sent = {k: v for k, v in seen["params"].items() if k in ("start", "end", "granularity")}
    assert sent == expected
