"""Protect prospective date provenance without changing historical packets."""

from copy import deepcopy

import pytest

from simba_mcp.evaluation.hosts import result_selection
from simba_mcp.evaluation.hosts.result_rlc_tasks import RLC_TASK_VERSION, rlc_development_tasks
from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch, development_tasks
from simba_mcp.server import create_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


DATED = ("result_roi", "result_tv_roi", "result_total_roi", "result_period_roi")


def task_named(name):
    return next(t for t in rlc_development_tasks() if t.id == name)


def test_prospective_windows_leave_historical_contracts_unchanged():
    assert RLC_TASK_VERSION == 2
    for old in development_tasks():
        if old.id in DATED:
            assert old.evidence_window is None
            assert not old.summary_granularity_independent
            new = task_named(old.id)
            assert new.expected == old.expected
            assert new.evidence_window["start"] == "2025-01-01"
            assert new.evidence_window["end"] == "2025-02-28"


@pytest.mark.anyio
@pytest.mark.parametrize("name", DATED)
@pytest.mark.parametrize("granularity", ("native", "month", "quarter"))
async def test_explicit_correct_date_range_accepts_summary_bucket(name, granularity):
    task = task_named(name)
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await dispatch(
        "get_model_results",
        {
            "model_hash": "result-example",
            "sections": "channel_summary,channel_map",
            "start": "2025-01-01",
            "end": "2025-02-28",
            "granularity": granularity,
        },
    )
    assert dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
@pytest.mark.parametrize("name", DATED)
@pytest.mark.parametrize(
    "window",
    (
        {"start": "2025-01-01", "end": "2025-01-31"},
        {"start": "2025-02-01", "end": "2025-02-28"},
        {"start": "2024-01-01", "end": "2024-02-28"},
        {},
    ),
)
async def test_wrong_or_unproven_summary_window_does_not_support_dates(name, window):
    task = task_named(name)
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await dispatch(
        "get_model_results",
        {
            "model_hash": "result-example",
            "sections": "channel_summary,channel_map",
            **window,
        },
    )
    assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_period_rows_establish_dates_without_explicit_request_window():
    task = task_named("result_period_roi")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await dispatch(
        "get_model_results", {"model_hash": "result-example", "sections": "coefficients"}
    )
    assert dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_incomplete_period_rows_do_not_pass_on_correct_final_number(monkeypatch):
    original = result_selection.run_case

    async def missing_second_period(case, **kwargs):
        case = case.model_copy(deep=True)
        payload = case.steps[0].exchanges[0].response
        payload["results"]["coefficients"] = [
            row for row in payload["results"]["coefficients"] if row["Date"] == 1735689600000
        ]
        return await original(case, **kwargs)

    monkeypatch.setattr(result_selection, "run_case", missing_second_period)
    task = task_named("result_period_roi")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await dispatch(
        "get_model_results", {"model_hash": "result-example", "sections": "coefficients"}
    )
    grade = dispatch.grade(task.expected)
    assert grade["facts"]
    assert not grade["required_evidence"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "name,start,end,wrong_start,wrong_end",
    (
        ("rlc01_attribution_absence", "2025-06-02", "2025-06-08", "2025-06-09", "2025-06-15"),
        ("result_overlap_value", "2025-01-01", "2025-01-31", "2025-02-01", "2025-02-28"),
    ),
)
async def test_first_row_evidence_accepts_only_requested_row(
    name, start, end, wrong_start, wrong_end
):
    task = task_named(name)
    for first, last, wanted in ((start, end, True), (wrong_start, wrong_end, False)):
        dispatch = ResultSelectionDispatch(create_server("compact"), task)
        await dispatch(
            "get_model_results",
            {
                "model_hash": dispatch.model_hash,
                "sections": "model_config,contributions",
                "start": first,
                "end": last,
            },
        )
        assert dispatch.grade(task.expected)["required_evidence"] is wanted


@pytest.mark.anyio
async def test_metadata_matching_window_cannot_hide_wrong_summary_values(monkeypatch):
    original = result_selection.run_case

    async def corrupt_summary(case, **kwargs):
        case = case.model_copy(deep=True)
        payload = case.steps[0].exchanges[0].response
        payload["results"]["channel_summary"][0]["Revenue"] = 200
        payload["results"]["channel_summary"][0]["Spend"] = 50
        payload["results"]["channel_summary"][0]["ROI"] = 4
        return await original(case, **kwargs)

    monkeypatch.setattr(result_selection, "run_case", corrupt_summary)
    task = task_named("result_roi")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await dispatch(
        "get_model_results",
        {
            "model_hash": "result-example",
            "sections": "channel_summary,channel_map",
            **deepcopy(task.evidence_window),
        },
    )
    assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
@pytest.mark.parametrize("name", ("result_roi", "result_tv_roi", "result_total_roi"))
async def test_dated_coefficients_are_an_alternative_to_summary(name):
    task = task_named(name)
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await dispatch(
        "get_model_results",
        {"model_hash": "result-example", "sections": "coefficients,channel_map"},
    )
    assert dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
@pytest.mark.parametrize("name", ("result_roi", "result_tv_roi", "result_total_roi"))
@pytest.mark.parametrize("removed", ("month", "channel"))
async def test_incomplete_coefficient_alternatives_are_rejected(monkeypatch, name, removed):
    original = result_selection.run_case
    task = task_named(name)

    async def incomplete(case, **kwargs):
        case = case.model_copy(deep=True)
        payload = case.steps[0].exchanges[0].response
        rows = payload["results"]["coefficients"]
        if removed == "month":
            rows = [row for row in rows if row["Date"] == 1735689600000]
        else:
            missing_channel = task.channel or "TV_activity"
            rows = [row for row in rows if row["Channel"] != missing_channel]
        payload["results"]["coefficients"] = rows
        return await original(case, **kwargs)

    monkeypatch.setattr(result_selection, "run_case", incomplete)
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await dispatch(
        "get_model_results",
        {"model_hash": "result-example", "sections": "coefficients,channel_map"},
    )
    assert not dispatch.grade(task.expected)["required_evidence"]
