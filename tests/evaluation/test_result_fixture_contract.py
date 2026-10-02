"""Synthetic invariants derived from verified saved-result API contracts."""

from collections import defaultdict
from copy import deepcopy

import pytest

from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch, result_tasks
from simba_mcp.evaluation.result_cases import saved_results, selected_payload, varied_results
from simba_mcp.server import create_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.parametrize("seed", [None, 7, 123, 456])
def test_every_total_has_consistent_underlying_rows(seed):
    payload = saved_results() if seed is None else varied_results(seed)
    rows = payload["results"]
    totals = defaultdict(lambda: defaultdict(float))
    for row in rows["coefficients"]:
        for key in ("Revenue", "Spend", "Sales"):
            totals[row["Channel"]][key] += row[key]
        assert row["ROI"] == row["Revenue"] / row["Spend"]
    for row in rows["channel_summary"]:
        assert all(row[k] == totals[row["Channel"]][k] for k in ("Revenue", "Spend", "Sales"))
        assert row["ROI"] == row["Revenue"] / row["Spend"]
    for row in rows["contributions"]:
        for channel in ("Search Activity", "TV_activity"):
            period = next(
                r
                for r in rows["coefficients"]
                if r["Date"] == row["Date"] and r["Channel"] == channel
            )
            assert row[channel] == period["Sales"]
        assert row["Model"] == sum(
            row[k] for k in ("Search Activity", "TV_activity", "Base", "price", "Overlap")
        )


def test_projection_metadata_and_absence_are_not_fabricated():
    assert "meta" not in selected_payload(["channel_summary"])
    missing = selected_payload(["unknown", "prediction_window"])
    assert missing["results"] == {} and missing["sections_available"] == []
    diagnostics = selected_payload(["model_stats", "r_hat", "model_config"])["results"]
    assert isinstance(diagnostics["model_stats"], list)
    assert diagnostics["model_config"]["config"]["link"] == "log"
    assert "mroi_periods" not in selected_payload([])["results"]


def test_native_window_recomputes_summary_without_requesting_periods():
    result = selected_payload(
        ["channel_summary", "mroi_summary"], start="2025-01-01", end="2025-01-31"
    )
    assert result["results"]["channel_summary"] == [
        {"Channel": "Search Activity", "Revenue": 200.0, "Spend": 50.0, "Sales": 20.0, "ROI": 4.0},
        {"Channel": "TV_activity", "Revenue": 150.0, "Spend": 50.0, "Sales": 15.0, "ROI": 3.0},
    ]
    assert isinstance(result["meta"]["not_windowed"], dict)
    assert result["results"]["mroi_summary"] == saved_results()["results"]["mroi_summary"]
    empty = selected_payload(["channel_summary", "coefficients"], start="2030-01-01")
    assert empty["results"] == {"channel_summary": [], "coefficients": []}
    with pytest.raises(ValueError):
        selected_payload([], start="2025-03-01", end="2025-01-01")


def test_historical_marginal_rows_preserved_and_disclosed():
    fixture = saved_results()
    periods = {
        "available": True,
        "rows": [{"date": "2024-01-01", "channel": "Search", "mroi_median": 1.2}],
    }
    fixture["results"]["mroi_periods"] = deepcopy(periods)
    assert (
        "mroi_periods" in selected_payload(["model_config"], fixture=fixture)["sections_available"]
    )
    result = selected_payload(["mroi_periods"], fixture=fixture, start="2025-01-01")
    assert result["results"]["mroi_periods"] == periods
    assert "mroi_periods" in result["meta"]["not_windowed"]


@pytest.mark.anyio
async def test_unknown_or_empty_filtered_results_do_not_establish_missing_diagnostics():
    task = result_tasks()[1]
    dispatch = ResultSelectionDispatch(create_server(), task)
    result, error = await dispatch(
        "get_model_results", {"model_hash": "result-example", "sections": "imaginary"}
    )
    assert not error and result["results"] == {}
    assert not dispatch.grade(task.expected)["required_evidence"]
    await dispatch(
        "get_model_results", {"model_hash": "result-example", "sections": "model_stats,r_hat"}
    )
    assert dispatch.grade(task.expected)["required_evidence"]
    assert "model_stats" not in result["results"]


@pytest.mark.anyio
async def test_wrong_window_cannot_support_a_guessed_full_window_total():
    task = result_tasks()[0]
    dispatch = ResultSelectionDispatch(create_server(), task)
    await dispatch(
        "get_model_results",
        {
            "model_hash": "result-example",
            "sections": "channel_summary,channel_map",
            "start": "2025-01-01",
            "end": "2025-01-31",
        },
    )
    assert dispatch.grade(task.expected)["facts"]
    assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_explicit_marginal_identity_is_sufficient_without_a_second_map_call():
    task = result_tasks()[2]
    dispatch = ResultSelectionDispatch(create_server(), task)
    await dispatch(
        "get_model_results", {"model_hash": "result-example", "sections": "mroi_summary"}
    )
    assert all(dispatch.grade({**task.expected, "channel": "Search"}).values())
    assert dispatch.noncontributing_result_calls == 0
    await dispatch("get_model_results", {"model_hash": "result-example", "sections": "imaginary"})
    assert dispatch.noncontributing_result_calls == 1


@pytest.mark.anyio
async def test_requesting_scorer_marker_does_not_prove_identity():
    task = result_tasks()[2]
    dispatch = ResultSelectionDispatch(create_server(), task)
    await dispatch(
        "get_model_results",
        {"model_hash": "result-example", "sections": "verified_channel_identity"},
    )
    assert "verified_channel_identity" not in dispatch.supported_sections
