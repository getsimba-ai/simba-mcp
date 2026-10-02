"""Independent rational arithmetic and saved-result acceptance coverage."""

from fractions import Fraction

import pytest

from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
from simba_mcp.evaluation.result_acceptance_v2 import acceptance_v2_tasks
from simba_mcp.evaluation.result_cases import selected_payload
from simba_mcp.server import create_server


def test_acceptance_v2_coverage_and_isolation():
    tasks = acceptance_v2_tasks()
    assert len(tasks) == 10
    assert len({t.id for t in tasks}) == 10
    assert len({t.family for t in tasks}) == 10
    assert len({t.dataset for t in tasks}) == 2
    assert all(not t.allow_prediction for t in tasks)
    assert all(t.fixture is not None and t.expected for t in tasks)
    tasks[0].fixture["results"].clear()
    assert tasks[1].fixture["results"]
    assert acceptance_v2_tasks()[0].fixture["results"]


def test_acceptance_v2_independent_arithmetic():
    expected = {t.family: t.expected for t in acceptance_v2_tasks()}
    leaf = Fraction(270 + 150, 180 + 60)
    seed = Fraction(120 + 270, 30 + 180)
    assert expected["window-roi"]["leaf_roi"] == float(leaf)
    assert expected["window-roi"]["seed_roi"] == round(float(seed), 6)
    assert expected["window-roi"]["roi_gap"] == round(float(seed - leaf), 6)
    assert expected["mean-median"]["difference"] == float(Fraction(17, 10) - Fraction(13, 10))
    assert expected["signed-reconciliation"]["before_overlap"] == 80 + 36 + 36 - 7
    assert expected["signed-reconciliation"]["model"] == 80 + 36 + 36 - 7 - 5
    assert expected["units-revenue"]["revenue_per_unit"] == Fraction(180, 36)
    assert expected["posterior-interval"]["width"] == float(Fraction(63, 100) - Fraction(19, 100))
    assert expected["diagnostic-attribution"]["excess"] == float(
        Fraction(108, 100) - Fraction(101, 100)
    )
    assert expected["decay-carryover"]["lag_two_retention"] == float(Fraction(1, 2) ** 2)


def test_acceptance_v2_alternative_window_evidence():
    task = acceptance_v2_tasks()[0]
    projected = selected_payload(["channel_summary"], fixture=task.fixture, **task.evidence_window)
    rows = {r["Channel"]: r for r in projected["results"]["channel_summary"]}
    assert rows["Leaf Activity"]["ROI"] == task.expected["leaf_roi"]
    assert round(rows["Seed Activity"]["ROI"], 6) == task.expected["seed_roi"]
    assert frozenset({"channel_summary"}) in task.evidence_sets()
    assert frozenset({"coefficients"}) in task.evidence_sets()


def test_acceptance_v2_sections_are_available():
    for task in acceptance_v2_tasks():
        for option in task.evidence_sets():
            projected = selected_payload(option, fixture=task.fixture)
            assert option <= projected["results"].keys()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("task", acceptance_v2_tasks(), ids=lambda task: task.id)
async def test_v2_all_sufficient_dispatcher_paths(task):
    for option in task.evidence_sets():
        dispatch = ResultSelectionDispatch(create_server("compact"), task)
        _, error = await dispatch(
            "get_model_results",
            {
                "model_hash": task.fixture["model_hash"],
                "sections": ",".join(sorted(option)),
                **(task.evidence_window or {}),
            },
        )
        assert not error
        assert all(dispatch.grade(task.expected).values())
        assert dispatch.unauthorised_read_attempts == 0


@pytest.mark.anyio
async def test_v2_wrong_model_refused_before_backend_access():
    task = acceptance_v2_tasks()[0]
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    _, error = await dispatch(
        "get_model_results", {"model_hash": "result-example", "sections": "coefficients"}
    )
    assert error
    assert dispatch.unauthorised_read_attempts == 1
    assert dispatch.actual_reads == 0
    assert not dispatch.grade(task.expected)["executed"]


@pytest.mark.anyio
async def test_v2_window_requires_both_channels_and_both_dates():
    task = acceptance_v2_tasks()[0]
    for arguments in [
        {"sections": "channel_summary"},
        {"sections": "coefficients", "start": "2025-04-14", "end": "2025-04-14"},
        {"sections": "coefficients", "channels": ["Leaf Activity"], **task.evidence_window},
        {"sections": "channel_summary", "channels": ["Leaf Activity"], **task.evidence_window},
    ]:
        dispatch = ResultSelectionDispatch(create_server("compact"), task)
        _, error = await dispatch(
            "get_model_results", {"model_hash": task.fixture["model_hash"], **arguments}
        )
        assert not error
        assert not dispatch.grade(task.expected)["required_evidence"]
    complete = ResultSelectionDispatch(create_server("compact"), task)
    _, error = await complete(
        "get_model_results", {"model_hash": task.fixture["model_hash"], "sections": "coefficients"}
    )
    assert not error
    assert all(complete.grade(task.expected).values())


@pytest.mark.anyio
async def test_v2_diagnostic_max_without_identity_is_insufficient():
    task = next(t for t in acceptance_v2_tasks() if t.family == "diagnostic-attribution")
    for sections in ("model_stats", "posterior", "model_stats,posterior"):
        dispatch = ResultSelectionDispatch(create_server("compact"), task)
        _, error = await dispatch(
            "get_model_results", {"model_hash": task.fixture["model_hash"], "sections": sections}
        )
        assert not error
        assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_v2_units_accepts_requested_period_and_rejects_other_period():
    task = next(t for t in acceptance_v2_tasks() if t.family == "units-revenue")
    for date, sufficient in [("2025-04-07", True), ("2025-04-14", False)]:
        dispatch = ResultSelectionDispatch(create_server("compact"), task)
        _, error = await dispatch(
            "get_model_results",
            {
                "model_hash": task.fixture["model_hash"],
                "sections": "contributions,coefficients",
                "start": date,
                "end": date,
            },
        )
        assert not error
        assert dispatch.grade(task.expected)["required_evidence"] is sufficient


@pytest.mark.anyio
async def test_v2_units_windowed_summary_supports_revenue_but_full_summary_does_not():
    task = next(t for t in acceptance_v2_tasks() if t.family == "units-revenue")
    for window, sufficient in [
        ({"start": "2025-04-07", "end": "2025-04-07"}, True),
        ({}, False),
        ({"start": "2025-04-07", "end": "2025-04-14"}, False),
    ]:
        dispatch = ResultSelectionDispatch(create_server("compact"), task)
        _, error = await dispatch(
            "get_model_results",
            {
                "model_hash": task.fixture["model_hash"],
                "sections": "contributions,channel_summary",
                **window,
            },
        )
        assert not error
        assert dispatch.grade(task.expected)["required_evidence"] is sufficient
