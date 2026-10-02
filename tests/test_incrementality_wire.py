"""Incrementality tests over the real MCP wire: each tool reaches its v1 route with exactly the
arguments given, a test read with a model_hash carries the derived row (or the refusal, as data),
imports are dry runs unless asked, create_model forwards calibration and keeps each refused
test's reason, a test design is queued, read in every result state and saved idempotently, and
each tool carries its declared effect. All values are synthetic."""

import json
from urllib.parse import parse_qs

import httpx
import pytest
from starlette.testclient import TestClient

from simba_mcp import runtime, server
from simba_mcp.api_client import SimbaAPIClient

TEST_ID = "5b0e8f7a-0000-4000-8000-000000000001"
RECORD = {
    "type": "geo",
    "name": "TV regional test",
    "status": "completed",
    "channel": "TV",
    "model_channel": "tv_grps",
    "kpi": {"kind": "revenue"},
    "start_date": "2026-03-02",
    "end_date": "2026-03-29",
    "result": {"lift_abs": 48000, "interval": {"low": 21000, "high": 75000, "level": 0.9}},
    "spend": {"incremental": 30000, "currency": "GBP"},
    "geo": {"treatment": ["North"], "control": ["South"]},
}
DETAIL = {
    "id": TEST_ID,
    "project_id": 7,
    "version": 1,
    "current_version": 1,
    "record": RECORD,
    "content_hash": "c" * 64,
    "used_by": [],
    "retired_at": None,
}
DERIVED = {
    "status": "ok",
    "row": {"channel": "tv_grps", "x": 900, "delta_x": 250, "delta_y": 12000, "sigma": 4103},
    "units": "revenue",
    "steps": [{"code": "per_period", "text": "48,000 over 4 test periods = 12,000 per period."}],
    "warnings": [],
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
    profile = "data_scientist" if tool == "create_model" else "marketer"
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


def _routes(responses):
    """Answer each request by path; record every request seen, in order."""
    seen = []

    def handle(request):
        seen.append(
            {
                "method": request.method,
                "path": request.url.path,
                "query": {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()},
                "body": json.loads(request.content) if request.content else None,
            }
        )
        status, body = responses[request.url.path]
        return httpx.Response(status, json=body)

    return seen, handle


def test_list_filters_and_pages(monkeypatch):
    path = "/api/v1/projects/7/incrementality-tests"
    seen, handle = _routes({path: (200, {"items": [], "next_cursor": None})})
    result = _call(
        monkeypatch,
        handle,
        "list_incrementality_tests",
        {"project_id": 7, "type": "geo", "status": "completed", "channel": "TV", "limit": 20},
    )
    assert result["structuredContent"] == {"items": [], "next_cursor": None}
    assert seen == [
        {
            "method": "GET",
            "path": path,
            "query": {"type": "geo", "status": "completed", "channel": "TV", "limit": "20"},
            "body": None,
        }
    ]


def test_priorities_passthrough_preserves_uncertainty_and_units(monkeypatch):
    path = "/api/v1/models/synthetic/test-priorities"
    body = {
        "method": "normal_binary_evpi_v1",
        "score_unit": "revenue_units",
        "items": [
            {
                "channel": "social",
                "score": 12.345,
                "reason_codes": ["prior_unavailable", "normal_approximation"],
            }
        ],
        "excluded": [{"channel": "search", "reason": "posterior_mean_unavailable"}],
    }
    seen, handle = _routes({path: (200, body)})
    result = _call(
        monkeypatch,
        handle,
        "recommend_incrementality_tests",
        {"model_hash": "synthetic", "budget": 1000, "hurdle": 1.2, "limit": 3},
    )
    assert result["structuredContent"] == body
    assert seen == [
        {
            "method": "GET",
            "path": path,
            "query": {"budget": "1000.0", "hurdle": "1.2", "limit": "3"},
            "body": None,
        }
    ]


def test_priorities_refusal_preserved(monkeypatch):
    path = "/api/v1/models/synthetic/test-priorities"
    seen, handle = _routes(
        {
            path: (
                422,
                {"error": "Stored summary unavailable", "code": "test_priorities_unavailable"},
            )
        }
    )
    result = _call(
        monkeypatch, handle, "recommend_incrementality_tests", {"model_hash": "synthetic"}
    )
    assert "test_priorities_unavailable" in json.dumps(result)
    assert len(seen) == 1


def test_get_without_a_model_reads_the_record_only(monkeypatch):
    seen, handle = _routes({f"/api/v1/incrementality-tests/{TEST_ID}": (200, DETAIL)})
    result = _call(monkeypatch, handle, "get_incrementality_test", {"test_id": TEST_ID})
    assert result["structuredContent"] == DETAIL
    assert [(r["method"], r["path"], r["query"]) for r in seen] == [
        ("GET", f"/api/v1/incrementality-tests/{TEST_ID}", {})
    ]


def test_get_with_a_model_adds_the_derived_row(monkeypatch):
    seen, handle = _routes(
        {
            f"/api/v1/incrementality-tests/{TEST_ID}": (200, DETAIL),
            f"/api/v1/incrementality-tests/{TEST_ID}/calibration": (200, DERIVED),
        }
    )
    result = _call(
        monkeypatch,
        handle,
        "get_incrementality_test",
        {
            "test_id": TEST_ID,
            "version": 1,
            "model_hash": "abc123",
            "channel": "tv_grps",
            "confirm_kpi": True,
        },
    )
    assert result["structuredContent"] == {**DETAIL, "calibration": DERIVED}
    assert seen[1]["query"] == {
        "version": "1",
        "model_hash": "abc123",
        "channel": "tv_grps",
        "confirm_kpi": "true",
    }


def test_a_refusal_is_an_answer_not_an_error(monkeypatch):
    refused = {
        "status": "refused",
        "reason": "kpi_mismatch",
        "message": "The test measured a different outcome from this model's KPI.",
        "steps": [],
    }
    seen, handle = _routes(
        {
            f"/api/v1/incrementality-tests/{TEST_ID}": (200, DETAIL),
            f"/api/v1/incrementality-tests/{TEST_ID}/calibration": (200, refused),
        }
    )
    result = _call(
        monkeypatch, handle, "get_incrementality_test", {"test_id": TEST_ID, "model_hash": "abc"}
    )
    assert not result.get("isError", False)
    assert result["structuredContent"]["calibration"] == refused
    assert "confirm_kpi" not in seen[1]["query"]


def test_an_unreadable_model_is_an_error(monkeypatch):
    _, handle = _routes(
        {
            f"/api/v1/incrementality-tests/{TEST_ID}": (200, DETAIL),
            f"/api/v1/incrementality-tests/{TEST_ID}/calibration": (
                404,
                {"error": "Model not found"},
            ),
        }
    )
    result = _call(
        monkeypatch, handle, "get_incrementality_test", {"test_id": TEST_ID, "model_hash": "gone"}
    )
    assert result["isError"] is True
    assert result["structuredContent"]["_status_code"] == 404


def test_a_missing_test_stops_before_the_model(monkeypatch):
    seen, handle = _routes(
        {f"/api/v1/incrementality-tests/{TEST_ID}": (404, {"error": "Test not found"})}
    )
    result = _call(
        monkeypatch, handle, "get_incrementality_test", {"test_id": TEST_ID, "model_hash": "abc"}
    )
    assert result["isError"] is True
    assert len(seen) == 1


def test_create_posts_the_record(monkeypatch):
    path = "/api/v1/projects/7/incrementality-tests"
    written = {"id": TEST_ID, "version": 1, "record": RECORD, "content_hash": "c" * 64}
    seen, handle = _routes({path: (201, written)})
    result = _call(
        monkeypatch, handle, "create_incrementality_test", {"project_id": 7, "record": RECORD}
    )
    assert result["structuredContent"] == written
    assert (seen[0]["method"], seen[0]["body"]) == ("POST", RECORD)


def test_import_is_a_dry_run_by_default(monkeypatch):
    path = "/api/v1/projects/7/incrementality-tests/import"
    preview = {
        "records": [{"key": "1", "record": {}, "errors": ["geo.channel: Field required"]}],
        "created": [],
        "notes": [],
    }
    seen, handle = _routes({path: (200, preview)})
    result = _call(
        monkeypatch,
        handle,
        "import_incrementality_tests",
        {"project_id": 7, "source": "geox", "content": "{}"},
    )
    assert result["structuredContent"] == preview
    assert seen[0]["body"] == {"source": "geox", "content": "{}", "dry_run": True}


def test_import_sends_defaults_and_overrides(monkeypatch):
    path = "/api/v1/projects/7/incrementality-tests/import"
    seen, handle = _routes({path: (200, {"records": [], "created": [TEST_ID], "notes": []})})
    defaults = {"channel": "TV", "model_channel": "tv_grps", "kpi": {"kind": "revenue"}}
    overrides = {"1": {"spend": {"incremental": 25000}}}
    _call(
        monkeypatch,
        handle,
        "import_incrementality_tests",
        {
            "project_id": 7,
            "source": "geox",
            "content": "{}",
            "dry_run": False,
            "defaults": defaults,
            "overrides": overrides,
        },
    )
    assert seen[0]["body"] == {
        "source": "geox",
        "content": "{}",
        "dry_run": False,
        "defaults": defaults,
        "overrides": overrides,
    }


def test_a_file_in_the_wrong_format_says_so(monkeypatch):
    path = "/api/v1/projects/7/incrementality-tests/import"
    _, handle = _routes(
        {path: (400, {"error": "The content is not valid JSON", "code": "import_invalid"})}
    )
    body = _call(
        monkeypatch,
        handle,
        "import_incrementality_tests",
        {"project_id": 7, "source": "meta_conversion_lift", "content": "a,b"},
    )["structuredContent"]
    assert body["_error_code"] == "import_invalid" and "source" in body["_next_action"]


_MODEL_ARGS = {
    "uploaded_file_id": 3,
    "date_column": "date",
    "kpi_column": "revenue",
    "hierarchy_column": "brand",
    "channels": [{"name": "TV", "activity_column": "tv_grps", "spend_column": "tv_spend"}],
}


def test_create_model_forwards_recorded_tests(monkeypatch):
    seen, handle = _routes({"/api/v1/models": (202, {"model_hash": "m1", "status": "queued"})})
    calibration = {"tests": [{"test_id": TEST_ID, "confirm_kpi": True}]}
    _call(monkeypatch, handle, "create_model", {**_MODEL_ARGS, "calibration": calibration})
    assert seen[0]["body"]["calibration"] == calibration


def test_create_model_forwards_direct_observations(monkeypatch):
    seen, handle = _routes({"/api/v1/models": (202, {"model_hash": "m2", "status": "queued"})})
    calibration = {
        "units": "revenue",
        "observations": [
            {"channel": "tv_grps", "x": 900, "delta_x": 250, "delta_y": 12000, "sigma": 4103}
        ],
    }
    _call(monkeypatch, handle, "create_model", {**_MODEL_ARGS, "calibration": calibration})
    assert seen[0]["body"]["calibration"] == calibration


def test_create_model_without_calibration_sends_none(monkeypatch):
    seen, handle = _routes({"/api/v1/models": (202, {"model_hash": "m3", "status": "queued"})})
    _call(monkeypatch, handle, "create_model", _MODEL_ARGS)
    assert "calibration" not in seen[0]["body"]


def test_a_refused_test_keeps_its_reason(monkeypatch):
    refusals = [
        {
            "test_id": TEST_ID,
            "reason": "channel_not_in_model",
            "message": "This model has no calibratable media channel for the test.",
        }
    ]
    _, handle = _routes(
        {
            "/api/v1/models": (
                422,
                {
                    "error": "Some tests can't calibrate this model",
                    "code": "calibration_refused",
                    "tests": refusals,
                },
            )
        }
    )
    result = _call(
        monkeypatch,
        handle,
        "create_model",
        {**_MODEL_ARGS, "calibration": {"tests": [{"test_id": TEST_ID}]}},
    )
    assert result["isError"] is True
    body = result["structuredContent"]
    assert body["_error_code"] == "calibration_refused"
    assert body["tests"] == refusals
    assert "channel" in body["_next_action"]


MODEL = "4d9bead326"
CALCULATION_ID = "tdc_7f3a9c2e1b"
DESIGNS = f"/api/v1/models/{MODEL}/test-designs"
DESIGN = f"{DESIGNS}/{CALCULATION_ID}"
DESIGN_ARGS = {
    "model_hash": MODEL,
    "submission_key": "design-2026-10-02-tv-pause-a1",
    "channel": "TV",
    "design_type": "time_holdout",
    "intervention": {
        "start_date": "2026-11-02",
        "durations": [4, 6, 8, 12],
        "spend_change": {"mode": "pause"},
        "baseline": {"mode": "recent_average", "periods": 13},
    },
}
QUEUED = {
    "calculation_id": CALCULATION_ID,
    "model_hash": MODEL,
    "status": "queued",
    "submitted_at": "2026-10-02T14:03:11Z",
}


def _calculation(result):
    return {
        **QUEUED,
        "status": "complete",
        "started_at": "2026-10-02T14:03:14Z",
        "completed_at": "2026-10-02T14:03:52Z",
        "request": {**DESIGN_ARGS, "inference": {"alpha": 0.1, "target_power": 0.8}},
        "error": None,
        "result": result,
    }


def test_design_is_queued_with_exactly_the_arguments_given(monkeypatch):
    seen, handle = _routes({DESIGNS: (202, QUEUED)})
    result = _call(monkeypatch, handle, "design_incrementality_test", DESIGN_ARGS)
    assert not result.get("isError", False)
    assert result["structuredContent"] == QUEUED
    assert seen == [
        {
            "method": "POST",
            "path": DESIGNS,
            "query": {},
            "body": {k: v for k, v in DESIGN_ARGS.items() if k != "model_hash"},
        }
    ]


def test_design_forwards_inference_and_geo_when_given(monkeypatch):
    seen, handle = _routes({DESIGNS: (202, QUEUED)})
    inference = {"alpha": 0.05, "named_effect": {"value": 150000, "estimand": "cumulative"}}
    geo = {
        "panel": {"kind": "uploaded_file", "id": 412, "sha256": "a" * 64},
        "columns": {"date": "week", "market": "region", "outcome": "sales"},
    }
    _call(
        monkeypatch,
        handle,
        "design_incrementality_test",
        {**DESIGN_ARGS, "design_type": "geo_split", "inference": inference, "geo": geo},
    )
    assert seen[0]["body"]["inference"] == inference
    assert seen[0]["body"]["geo"] == geo
    assert seen[0]["body"]["design_type"] == "geo_split"


def test_a_repeated_key_with_different_inputs_is_an_error(monkeypatch):
    _, handle = _routes(
        {
            DESIGNS: (
                409,
                {
                    "error": "submission_key was used with different inputs",
                    "code": "submission_key_conflict",
                },
            )
        }
    )
    result = _call(monkeypatch, handle, "design_incrementality_test", DESIGN_ARGS)
    assert result["isError"] is True
    body = result["structuredContent"]
    assert body["_status_code"] == 409 and body["_error_code"] == "submission_key_conflict"


AVAILABLE = {
    "state": "available",
    "design_type": "time_holdout",
    "channel": "TV",
    "reasons": [],
    "warnings": ["no_out_of_sample_calibration"],
    "model_implied_effect": {"available": True, "mean": -310000, "hdi_3": -520000},
    "detectable_effect": {"alpha": 0.1, "target_power": 0.8, "cumulative_mde": 286000},
    "power": {"at_model_mean_effect": {"power": 0.853}, "assurance": {"value": 0.74}},
    "candidates": [{"duration_periods": 8, "selected": True}],
}
NOT_AVAILABLE = {
    "unsupported": [{"code": "unsupported_model_family", "detail": "log"}],
    "insufficient_evidence": [{"code": "training_periods_too_few", "detail": "20"}],
    "no_feasible_design": [{"code": "target_power_not_reached", "detail": "0.31"}],
}


def test_an_available_result_is_read_as_data(monkeypatch):
    calculation = _calculation(AVAILABLE)
    seen, handle = _routes({DESIGN: (200, calculation)})
    result = _call(
        monkeypatch,
        handle,
        "get_incrementality_test_design",
        {"model_hash": MODEL, "calculation_id": CALCULATION_ID},
    )
    assert not result.get("isError", False)
    assert result["structuredContent"] == calculation
    assert result["structuredContent"]["result"]["power"]["assurance"]["value"] == 0.74
    assert [(r["method"], r["path"], r["query"]) for r in seen] == [("GET", DESIGN, {})]


@pytest.mark.parametrize("state", sorted(NOT_AVAILABLE))
def test_a_result_that_is_not_available_is_an_answer_not_an_error(monkeypatch, state):
    unavailable = {
        "state": state,
        "design_type": "time_holdout",
        "channel": "TV",
        "reasons": NOT_AVAILABLE[state],
        "warnings": [],
        "assumptions": [],
    }
    _, handle = _routes({DESIGN: (200, _calculation(unavailable))})
    result = _call(
        monkeypatch,
        handle,
        "get_incrementality_test_design",
        {"model_hash": MODEL, "calculation_id": CALCULATION_ID},
    )
    assert not result.get("isError", False)
    body = result["structuredContent"]["result"]
    assert body["state"] == state and body["reasons"] == NOT_AVAILABLE[state]
    assert "power" not in body and "detectable_effect" not in body


def test_a_queued_calculation_has_no_result_yet(monkeypatch):
    _, handle = _routes({DESIGN: (200, {**QUEUED, "result": None, "error": None})})
    result = _call(
        monkeypatch,
        handle,
        "get_incrementality_test_design",
        {"model_hash": MODEL, "calculation_id": CALCULATION_ID},
    )
    assert not result.get("isError", False)
    assert result["structuredContent"]["status"] == "queued"
    assert result["structuredContent"]["result"] is None


PLANNED = {
    "id": TEST_ID,
    "version": 1,
    "record": {
        "type": "time_holdout",
        "name": "TV pause, 8 weeks from 2 Nov 2026 (planned)",
        "status": "planned",
        "channel": "TV",
        "source": {"tool": "design", "fields": {"calculation_id": CALCULATION_ID}},
        "time_holdout": {
            "counterfactual": "model_forecast",
            "analysis_method": "forecast_contrast_v1",
            "carryover_periods": 3,
        },
    },
    "content_hash": "d" * 64,
}


def test_save_sends_only_the_target_and_name(monkeypatch):
    seen, handle = _routes({f"{DESIGN}/save": (201, PLANNED)})
    result = _call(
        monkeypatch,
        handle,
        "save_incrementality_test_design",
        {"model_hash": MODEL, "calculation_id": CALCULATION_ID, "project_id": 7, "name": "TV"},
    )
    assert not result.get("isError", False)
    assert result["structuredContent"] == PLANNED
    assert result["structuredContent"]["record"]["status"] == "planned"
    assert "result" not in result["structuredContent"]["record"]
    assert seen == [
        {
            "method": "POST",
            "path": f"{DESIGN}/save",
            "query": {},
            "body": {"project_id": 7, "name": "TV"},
        }
    ]


def test_save_again_returns_the_same_record(monkeypatch):
    seen, handle = _routes({f"{DESIGN}/save": (200, PLANNED)})
    result = _call(
        monkeypatch,
        handle,
        "save_incrementality_test_design",
        {"model_hash": MODEL, "calculation_id": CALCULATION_ID},
    )
    assert not result.get("isError", False)
    assert result["structuredContent"] == PLANNED
    assert seen[0]["body"] == {}


def test_save_of_an_unavailable_result_is_an_error(monkeypatch):
    _, handle = _routes(
        {
            f"{DESIGN}/save": (
                409,
                {"error": "The result is not available", "code": "result_not_available"},
            )
        }
    )
    result = _call(
        monkeypatch,
        handle,
        "save_incrementality_test_design",
        {"model_hash": MODEL, "calculation_id": CALCULATION_ID},
    )
    assert result["isError"] is True
    assert result["structuredContent"]["_error_code"] == "result_not_available"


def test_each_tool_declares_its_effect():
    from tests.test_server import _list_tools

    tools = {t.name: t.annotations for t in _list_tools()}
    for name in (
        "list_incrementality_tests",
        "get_incrementality_test",
        "get_incrementality_test_design",
    ):
        assert tools[name].read_only_hint is True
    for name in ("create_incrementality_test", "import_incrementality_tests"):
        hints = tools[name]
        assert (hints.read_only_hint, hints.destructive_hint, hints.idempotent_hint) == (
            False,
            False,
            False,
        )
    for name in ("design_incrementality_test", "save_incrementality_test_design"):
        hints = tools[name]
        assert (hints.read_only_hint, hints.destructive_hint, hints.idempotent_hint) == (
            False,
            False,
            True,
        )
