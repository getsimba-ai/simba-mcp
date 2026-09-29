"""Independent V4 evidence sufficiency and authority checks, no provider calls."""

import pytest

from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
from simba_mcp.evaluation.result_acceptance_v4 import acceptance_v4_tasks
from simba_mcp.server import create_server


def task_named(suffix):
    return next(task for task in acceptance_v4_tasks() if task.id == "v4_" + suffix)


async def read(dispatch, sections, **kwargs):
    result, error = await dispatch(
        "get_model_results",
        {"model_hash": dispatch.model_hash, "sections": sections, **kwargs},
    )
    assert not error, result
    return result


@pytest.mark.anyio
@pytest.mark.parametrize("task", acceptance_v4_tasks(), ids=lambda task: task.id)
async def test_v4_every_declared_evidence_path(task):
    for option in task.evidence_sets():
        dispatch = ResultSelectionDispatch(create_server("compact"), task)
        await read(dispatch, ",".join(sorted(option)), **(task.evidence_window or {}))
        assert all(dispatch.grade(task.expected).values()), dispatch.supported_sections


@pytest.mark.anyio
@pytest.mark.parametrize(
    "suffix,channel",
    [("marginal_average", "Leaflet_activity"), ("missing_optional", "Cinema_activity")],
)
async def test_v4_target_channel_marginal_evidence(suffix, channel):
    task = task_named(suffix)
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await read(dispatch, ",".join(sorted(task.required_sections)), channels=[channel])
    assert dispatch.grade(task.expected)["required_evidence"]
    wrong = ResultSelectionDispatch(create_server("compact"), task)
    await read(wrong, ",".join(sorted(task.required_sections)), channels=["unmatched"])
    assert not wrong.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_v4_window_requires_both_media_and_correct_periods():
    task = task_named("window_weighted")
    for window, channels in [({}, None), (task.evidence_window, ["Leaflet_activity"])]:
        dispatch = ResultSelectionDispatch(create_server("compact"), task)
        await read(
            dispatch,
            "channel_summary,channel_map",
            **window,
            **({"channels": channels} if channels else {}),
        )
        assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "window",
    [
        {"granularity": "month"},
        {"granularity": "month", "start": "2025-06-01", "end": "2025-06-30"},
    ],
)
async def test_v4_equivalent_monthly_windows(window):
    task = task_named("uncertainty_aggregation")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await read(dispatch, "actual_vs_model", **window)
    assert dispatch.grade(task.expected)["required_evidence"]
    native = ResultSelectionDispatch(create_server("compact"), task)
    await read(native, "actual_vs_model")
    assert not native.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "sections", ["", "actual_vs_model,coefficients,contributions,channel_summary,mroi_summary"]
)
async def test_v4_monthly_default_and_bundled_sections_are_lawful(sections):
    task = task_named("uncertainty_aggregation")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    result = await read(dispatch, sections, granularity="month")
    assert dispatch.grade(task.expected)["required_evidence"]
    assert result["results"]["actual_vs_model"] == [
        {"period_start": "2025-06-01", "period_end": "2025-06-30", "Actual": 264, "Model": 260}
    ]
    assert sum(row["Revenue"] for row in result["results"]["coefficients"]) == 800
    assert sum(row["Spend"] for row in result["results"]["coefficients"]) == 576
    assert result["results"]["contributions"][0]["Model"] == 260
    assert "prediction_window" not in result["results"]


@pytest.mark.anyio
@pytest.mark.parametrize("forbidden_section", ["prediction_window", "predictions"])
async def test_v4_authority_allows_safe_extras_but_refuses_prediction(forbidden_section):
    task = task_named("read_authority")
    for sections in ("channel_summary,channel_map,model_config", ""):
        dispatch = ResultSelectionDispatch(create_server("compact"), task)
        result = await read(dispatch, sections)
        assert "prediction_window" not in result["results"]
        assert dispatch.grade(task.expected)["required_evidence"]
        assert dispatch.unauthorised_read_attempts == 0
    forbidden = ResultSelectionDispatch(create_server("compact"), task)
    _, error = await forbidden(
        "get_model_results", {"model_hash": forbidden.model_hash, "sections": forbidden_section}
    )
    assert error and forbidden.unauthorised_read_attempts == 1
    assert forbidden.actual_reads == forbidden.unauthorised_reads == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "suffix,start,end",
    [
        ("signed_reconciliation", "2025-02-03", "2025-02-10"),
        ("attribution_absence", "2025-06-02", "2025-06-02"),
    ],
)
async def test_v4_only_requested_contribution_periods_are_needed(suffix, start, end):
    task = task_named(suffix)
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await read(dispatch, "contributions", start=start, end=end)
    await read(dispatch, "model_config,channel_summary")
    assert dispatch.grade(task.expected)["required_evidence"]
    wrong = ResultSelectionDispatch(create_server("compact"), task)
    await read(wrong, "contributions", start="2025-02-17", end="2025-02-24")
    await read(wrong, "model_config,channel_summary")
    assert not wrong.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_v4_split_channel_identity_and_summary_reads_accumulate():
    task = task_named("identity_comparison")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    for channel in ("Retail Radio_activity", "Cinema_activity"):
        await read(dispatch, "channel_map,channel_summary", channels=[channel])
    assert dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_v4_weekly_coefficients_preserve_requested_window_evidence():
    task = task_named("window_weighted")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await read(
        dispatch,
        "channel_map,coefficients",
        start="2025-02-10",
        end="2025-02-17",
        granularity="week",
    )
    assert dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
@pytest.mark.parametrize("bucket", ["month", "quarter"])
async def test_v4_aggregate_coefficient_buckets_are_sufficient_only_for_correct_window(bucket):
    task = task_named("window_weighted")
    for window, sufficient in [
        ({"start": "2025-02-10", "end": "2025-02-17"}, True),
        ({}, False),
        ({"start": "2025-02-03", "end": "2025-02-10"}, False),
    ]:
        dispatch = ResultSelectionDispatch(create_server("compact"), task)
        await read(dispatch, "channel_map,coefficients", granularity=bucket, **window)
        assert dispatch.grade(task.expected)["required_evidence"] is sufficient


@pytest.mark.anyio
@pytest.mark.parametrize("bucket", ["month", "quarter"])
async def test_v4_full_period_aggregate_coefficient_buckets_preserve_channel_roi(bucket):
    task = task_named("identity_comparison")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await read(dispatch, "channel_map,coefficients", granularity=bucket)
    assert dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_v4_weekly_contributions_preserve_individual_weeks_but_month_does_not():
    task = task_named("signed_reconciliation")
    for bucket, sufficient in [("week", True), ("month", False), ("quarter", False)]:
        dispatch = ResultSelectionDispatch(create_server("compact"), task)
        await read(
            dispatch, "contributions", start="2025-02-03", end="2025-02-10", granularity=bucket
        )
        await read(dispatch, "model_config,channel_summary")
        assert dispatch.grade(task.expected)["required_evidence"] is sufficient
