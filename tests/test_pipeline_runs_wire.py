"""Pipeline runs and schedules over the real MCP wire: run_pipeline, get_pipeline_run and
set_pipeline_schedule reach their v1 routes with exactly the arguments given, a second start
comes back as run_in_progress with its run_id and a next action, and each tool carries the
declared effect."""

import json

import httpx
from starlette.testclient import TestClient

from simba_mcp import runtime, server
from simba_mcp.api_client import SimbaAPIClient

RUN = {
    "run_id": 41,
    "status": "succeeded",
    "started_at": "2026-09-28T06:00:02",
    "finished_at": "2026-09-28T06:01:40",
    "version_id": 212,
    "error_code": None,
    "error": None,
}
SCHEDULE = {
    "cadence": "weekly",
    "hour_utc": 6,
    "weekday": 0,
    "enabled": True,
    "next_run_at": "2026-10-05T06:00:00",
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
    with TestClient(server._create_app()) as client:
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


def _recorder(status, body):
    seen = {}

    def handle(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content) if request.content else None
        return httpx.Response(status, json=body)

    return seen, handle


def test_run_pipeline_queues_with_the_date_range(monkeypatch):
    seen, handle = _recorder(202, {"run_id": 41, "status": "queued"})
    result = _call(
        monkeypatch,
        handle,
        "run_pipeline",
        {"pipeline_ref": "ab12cd34ef", "start_date": "2026-01-01", "end_date": "2026-03-31"},
    )
    assert not result.get("isError", False)
    assert result["structuredContent"] == {"run_id": 41, "status": "queued"}
    assert (seen["method"], seen["path"]) == ("POST", "/api/v1/pipelines/ab12cd34ef/runs")
    assert seen["body"] == {"start_date": "2026-01-01", "end_date": "2026-03-31"}


def test_run_pipeline_without_dates_sends_an_empty_body(monkeypatch):
    seen, handle = _recorder(202, {"run_id": 42, "status": "queued"})
    _call(monkeypatch, handle, "run_pipeline", {"pipeline_ref": "ab12cd34ef"})
    assert seen["body"] == {}


def test_a_second_start_points_at_the_active_run(monkeypatch):
    _, handle = _recorder(
        409,
        {
            "error": "A run of this pipeline is already queued or running.",
            "code": "run_in_progress",
            "run_id": 41,
        },
    )
    result = _call(monkeypatch, handle, "run_pipeline", {"pipeline_ref": "ab12cd34ef"})
    assert result["isError"] is True
    body = result["structuredContent"]
    assert (body["_error_code"], body["run_id"]) == ("run_in_progress", 41)
    assert "get_pipeline_run" in body["_next_action"]


def test_queue_unavailable_says_to_retry_later(monkeypatch):
    _, handle = _recorder(
        503, {"error": "The run could not be queued", "code": "queue_unavailable"}
    )
    body = _call(monkeypatch, handle, "run_pipeline", {"pipeline_ref": "p"})["structuredContent"]
    assert (
        body["_error_code"] == "queue_unavailable" and "run_pipeline again" in body["_next_action"]
    )


def test_get_pipeline_run_reads_one_run(monkeypatch):
    seen, handle = _recorder(200, RUN)
    result = _call(
        monkeypatch, handle, "get_pipeline_run", {"pipeline_ref": "ab12cd34ef", "run_id": 41}
    )
    assert result["structuredContent"] == RUN
    assert (seen["method"], seen["path"]) == ("GET", "/api/v1/pipelines/ab12cd34ef/runs/41")


def test_set_pipeline_schedule_replaces_it(monkeypatch):
    seen, handle = _recorder(200, SCHEDULE)
    result = _call(
        monkeypatch,
        handle,
        "set_pipeline_schedule",
        {
            "pipeline_ref": "ab12cd34ef",
            "cadence": "weekly",
            "hour_utc": 6,
            "weekday": 0,
            "enabled": True,
        },
    )
    assert result["structuredContent"] == SCHEDULE
    assert (seen["method"], seen["path"]) == ("PUT", "/api/v1/pipelines/ab12cd34ef/schedule")
    assert seen["body"] == {"cadence": "weekly", "hour_utc": 6, "weekday": 0, "enabled": True}


def test_a_daily_schedule_sends_no_weekday(monkeypatch):
    seen, handle = _recorder(200, {**SCHEDULE, "cadence": "daily", "weekday": None})
    _call(
        monkeypatch,
        handle,
        "set_pipeline_schedule",
        {"pipeline_ref": "p", "cadence": "daily", "hour_utc": 7, "enabled": False},
    )
    assert seen["body"] == {"cadence": "daily", "hour_utc": 7, "enabled": False}


def test_each_tool_declares_its_effect():
    from tests.test_server import _list_tools

    tools = {t.name: t.annotations for t in _list_tools()}
    run, poll, schedule = (
        tools["run_pipeline"],
        tools["get_pipeline_run"],
        tools["set_pipeline_schedule"],
    )
    assert (run.read_only_hint, run.destructive_hint, run.idempotent_hint) == (False, False, False)
    assert poll.read_only_hint is True
    assert (schedule.read_only_hint, schedule.destructive_hint, schedule.idempotent_hint) == (
        False,
        True,
        True,
    )
