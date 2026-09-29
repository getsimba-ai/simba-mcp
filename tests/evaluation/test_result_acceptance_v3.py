"""Arithmetic and public saved-result contract checks for the third acceptance packet."""

import re
from fractions import Fraction

import pytest

from simba_mcp.evaluation.result_acceptance_v3 import (
    RUBRICS,
    acceptance_v3_tasks,
    independent_oracles,
)
from simba_mcp.evaluation.result_cases import selected_payload


def test_acceptance_v3_coverage_and_task_contract():
    tasks = acceptance_v3_tasks()
    assert len(tasks) == len({task.id for task in tasks}) == 10
    assert len({task.family for task in tasks}) == 10
    assert len({task.dataset for task in tasks}) == 2
    assert "diagnostic_parameter_scope" in {task.family for task in tasks}
    for task in tasks:
        assert re.fullmatch(r"[a-z][a-z0-9_]+", task.id)
        assert task.fixture["model_hash"] in task.prompt
        assert RUBRICS[task.id]["explanation"]
        assert not task.allow_prediction


@pytest.mark.parametrize("task", acceptance_v3_tasks(), ids=lambda task: task.id)
def test_acceptance_v3_independent_exact_arithmetic(task):
    for field, exact in independent_oracles().get(task.id, {}).items():
        assert task.expected[field] == pytest.approx(float(exact), abs=1e-12)


@pytest.mark.parametrize("task", acceptance_v3_tasks(), ids=lambda task: task.id)
def test_acceptance_v3_sufficient_sections_survive_projection(task):
    for sections in task.evidence_sets():
        physical = set(sections)
        if "verified_media_identity" in physical:
            physical.remove("verified_media_identity")
            physical.add("channel_map")
        if "period_revenue_rows" in physical:
            physical.remove("period_revenue_rows")
            physical.add("coefficients")
        result = selected_payload(physical, fixture=task.fixture, **(task.evidence_window or {}))
        assert physical <= result["results"].keys()


def test_acceptance_v3_diagnostic_rows_cover_transform_parameter():
    task = next(
        task for task in acceptance_v3_tasks() if task.family == "diagnostic_parameter_scope"
    )
    results = task.fixture["results"]
    rows = results["r_hat"]
    maximum = max(rows, key=lambda row: row["R_hat"])
    assert maximum["Parameter"] == task.expected["max_parameter"]
    assert maximum["R_hat"] == task.expected["max_r_hat"]
    assert results["model_stats"][0]["Output"] == maximum["R_hat"]
    assert sum(Fraction(str(row["R_hat"])) > Fraction(101, 100) for row in rows) == 1


def test_acceptance_v3_period_window_is_not_mroi_aggregation():
    task = next(task for task in acceptance_v3_tasks() if task.family == "historical_mroi_scope")
    result = selected_payload(task.required_sections, fixture=task.fixture, **task.evidence_window)
    assert len(result["results"]["mroi_periods"]["rows"]) == 3
    assert "mroi_periods" in result["meta"]["not_windowed"]
    row = next(
        row
        for row in result["results"]["mroi_periods"]["rows"]
        if row["date"] == task.evidence_window["start"]
    )
    assert row["mroi_median"] == task.expected["median"]


def test_acceptance_v3_returned_fixtures_are_isolated():
    first = acceptance_v3_tasks()
    first[0].fixture["results"].clear()
    assert acceptance_v3_tasks()[0].fixture["results"]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("task", acceptance_v3_tasks(), ids=lambda task: task.id)
async def test_v3_all_declared_dispatcher_paths(task):
    from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
    from simba_mcp.server import create_server

    for option in task.evidence_sets():
        option = set(option)
        if "verified_media_identity" in option:
            option.remove("verified_media_identity")
            option.add("channel_map")
        if "period_revenue_rows" in option:
            option.remove("period_revenue_rows")
            option.add("coefficients")
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
        assert dispatch.actual_reads == 1
        assert dispatch.unauthorised_read_attempts == 0


@pytest.mark.anyio
async def test_v3_window_rejects_wrong_totals_or_missing_periods():
    from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
    from simba_mcp.server import create_server

    task = next(t for t in acceptance_v3_tasks() if t.id == "v3_window_aggregate")
    for request in [
        {"sections": "channel_summary"},
        {"sections": "channel_summary", "start": "2025-02-03", "end": "2025-02-03"},
        {"sections": "coefficients", "start": "2025-02-10", "end": "2025-02-10"},
        {"sections": "coefficients", "channels": ["cinema_activity"]},
    ]:
        dispatch = ResultSelectionDispatch(create_server("compact"), task)
        _, error = await dispatch(
            "get_model_results", {"model_hash": task.fixture["model_hash"], **request}
        )
        assert not error
        assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_v3_diagnostic_max_does_not_supply_threshold_count():
    from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
    from simba_mcp.server import create_server

    task = next(t for t in acceptance_v3_tasks() if t.id == "v3_diagnostic_parameter_scope")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await dispatch(
        "get_model_results", {"model_hash": task.fixture["model_hash"], "sections": "model_stats"}
    )
    assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_v3_headline_is_not_historical_evidence():
    from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
    from simba_mcp.server import create_server

    for task in acceptance_v3_tasks():
        if task.id not in {"v3_historical_mroi_scope", "v3_optional_history_absent"}:
            continue
        dispatch = ResultSelectionDispatch(create_server("compact"), task)
        await dispatch(
            "get_model_results",
            {"model_hash": task.fixture["model_hash"], "sections": "mroi_summary"},
        )
        assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "sections",
    [
        ("coefficients", "coefficients"),
        ("channel_summary", "channel_summary"),
        ("coefficients", "channel_summary"),
    ],
)
async def test_v3_individual_date_evidence_accumulates(sections):
    from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
    from simba_mcp.server import create_server

    task = next(t for t in acceptance_v3_tasks() if t.id == "v3_kpi_revenue_basis")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    for index, (date, section) in enumerate(
        zip(["2025-02-03", "2025-02-10"], sections, strict=True)
    ):
        _, error = await dispatch(
            "get_model_results",
            {
                "model_hash": task.fixture["model_hash"],
                "sections": section,
                "start": date,
                "end": date,
                "channels": ["radio_activity"],
            },
        )
        assert not error
        assert dispatch.grade(task.expected)["required_evidence"] is (index == 1)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "windows",
    [
        (("2025-02-03", "2025-02-10"),),
        (("2025-02-03", "2025-02-03"), ("2025-02-03", "2025-02-03")),
        (("2025-02-03", "2025-02-03"), ("2025-02-17", "2025-02-17")),
    ],
)
async def test_v3_summary_aggregate_duplicates_wrong_dates_do_not_supply_period_factors(windows):
    from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
    from simba_mcp.server import create_server

    task = next(t for t in acceptance_v3_tasks() if t.id == "v3_kpi_revenue_basis")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    for start, end in windows:
        await dispatch(
            "get_model_results",
            {
                "model_hash": task.fixture["model_hash"],
                "sections": "channel_summary",
                "start": start,
                "end": end,
                "channels": ["radio_activity"],
            },
        )
    assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
@pytest.mark.parametrize("section", ["channel_map", "channel_summary", "coefficients"])
async def test_v3_identity_can_be_unwindowed_and_separate_from_decomposition(section):
    from dataclasses import replace

    from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
    from simba_mcp.server import create_server

    task = next(t for t in acceptance_v3_tasks() if t.id == "v3_signed_reconciliation")
    # Exercise the stricter virtual identity marker separately from the actual
    # prompt, whose explicit component partition also allows contributions alone.
    task = replace(
        task, evidence_options=(frozenset({"contributions", "verified_media_identity"}),)
    )
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await dispatch(
        "get_model_results",
        {
            "model_hash": task.fixture["model_hash"],
            "sections": "contributions",
            **task.evidence_window,
        },
    )
    assert not dispatch.grade(task.expected)["required_evidence"]
    await dispatch(
        "get_model_results", {"model_hash": task.fixture["model_hash"], "sections": section}
    )
    assert all(dispatch.grade(task.expected).values())


@pytest.mark.anyio
async def test_v3_identity_needs_both_media_channels():
    from dataclasses import replace

    from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
    from simba_mcp.server import create_server

    task = next(t for t in acceptance_v3_tasks() if t.id == "v3_signed_reconciliation")
    # Exercise the stricter virtual identity marker separately from the actual
    # prompt, whose explicit component partition also allows contributions alone.
    task = replace(
        task, evidence_options=(frozenset({"contributions", "verified_media_identity"}),)
    )
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await dispatch(
        "get_model_results",
        {
            "model_hash": task.fixture["model_hash"],
            "sections": "contributions",
            **task.evidence_window,
        },
    )
    for index, channel in enumerate(["radio_activity", "cinema_activity"]):
        await dispatch(
            "get_model_results",
            {
                "model_hash": task.fixture["model_hash"],
                "sections": "channel_summary",
                "channels": [channel],
            },
        )
        assert dispatch.grade(task.expected)["required_evidence"] is (index == 1)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "sections",
    ["prediction_window", "model_config", "coefficients", "channel_summary,prediction_window", ""],
)
async def test_v3_explicit_summary_only_scope_refuses_other_reads(sections):
    from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
    from simba_mcp.server import create_server

    task = next(t for t in acceptance_v3_tasks() if t.id == "v3_prediction_access_boundary")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    _, error = await dispatch(
        "get_model_results", {"model_hash": task.fixture["model_hash"], "sections": sections}
    )
    assert error
    assert dispatch.read_attempts == dispatch.unauthorised_read_attempts == 1
    assert dispatch.actual_reads == dispatch.unauthorised_reads == 0
    assert not dispatch.grade(task.expected)["executed"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "task_id,marker",
    [
        ("v3_kpi_revenue_basis", "period_revenue_rows"),
        ("v3_signed_reconciliation", "verified_media_identity"),
    ],
)
async def test_v3_virtual_marker_names_do_not_supply_evidence(task_id, marker):
    from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
    from simba_mcp.server import create_server

    task = next(t for t in acceptance_v3_tasks() if t.id == task_id)
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await dispatch(
        "get_model_results", {"model_hash": task.fixture["model_hash"], "sections": marker}
    )
    assert marker not in dispatch.supported_sections
    assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_v3_wrong_channel_summaries_do_not_supply_requested_periods():
    from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
    from simba_mcp.server import create_server

    task = next(t for t in acceptance_v3_tasks() if t.id == "v3_kpi_revenue_basis")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    for date in ["2025-02-03", "2025-02-10"]:
        await dispatch(
            "get_model_results",
            {
                "model_hash": task.fixture["model_hash"],
                "sections": "channel_summary",
                "channels": ["cinema_activity"],
                "start": date,
                "end": date,
            },
        )
    assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_v3_wrong_summary_value_is_not_verified(monkeypatch):
    from simba_mcp.evaluation.hosts import result_selection
    from simba_mcp.server import create_server

    original = result_selection.selected_payload

    def changed_summary(sections, **kwargs):
        payload = original(sections, **kwargs)
        for row in payload["results"].get("channel_summary", []):
            row["Revenue"] += 1
        return payload

    monkeypatch.setattr(result_selection, "selected_payload", changed_summary)
    task = next(t for t in acceptance_v3_tasks() if t.id == "v3_kpi_revenue_basis")
    dispatch = result_selection.ResultSelectionDispatch(create_server("compact"), task)
    for date in ["2025-02-03", "2025-02-10"]:
        await dispatch(
            "get_model_results",
            {
                "model_hash": task.fixture["model_hash"],
                "sections": "channel_summary",
                "start": date,
                "end": date,
            },
        )
    assert "period_revenue_rows" not in dispatch.supported_sections
    assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
@pytest.mark.parametrize("section", ["coefficients", "channel_summary"])
async def test_v3_full_period_channel_comparison_accepts_split_and_repeated_rows(section):
    from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
    from simba_mcp.server import create_server

    task = next(t for t in acceptance_v3_tasks() if t.id == "v3_channel_comparison")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    for index, channel in enumerate(["audio_activity", "audio_activity", "print_activity"]):
        await dispatch(
            "get_model_results",
            {"model_hash": task.fixture["model_hash"], "sections": section, "channels": [channel]},
        )
        assert dispatch.grade(task.expected)["required_evidence"] is (index == 2)


@pytest.mark.anyio
async def test_v3_summary_union_does_not_mix_date_contexts():
    from dataclasses import replace

    from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
    from simba_mcp.server import create_server

    original = next(t for t in acceptance_v3_tasks() if t.id == "v3_channel_comparison")
    task = replace(original, evidence_window={"start": "2025-05-05", "end": "2025-05-12"})
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    requests = [
        {"channels": ["print_activity"], **task.evidence_window},
        {"channels": ["audio_activity"], "start": "2025-05-05", "end": "2025-05-05"},
        {"channels": ["audio_activity"], **task.evidence_window},
    ]
    for index, request in enumerate(requests):
        await dispatch(
            "get_model_results",
            {"model_hash": task.fixture["model_hash"], "sections": "channel_summary", **request},
        )
        assert dispatch.grade(task.expected)["required_evidence"] is (index == 2)
