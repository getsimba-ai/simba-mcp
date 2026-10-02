"""Independent rational arithmetic and contract checks for fresh synthetic labels."""

from fractions import Fraction

import pytest

from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
from simba_mcp.evaluation.result_acceptance_fresh import fresh_acceptance_tasks
from simba_mcp.evaluation.result_cases import selected_payload
from simba_mcp.server import create_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_fresh_coverage_and_isolation():
    tasks = fresh_acceptance_tasks()
    assert len(tasks) == len({t.id for t in tasks}) == len({t.family for t in tasks}) == 8
    assert len({t.dataset for t in tasks}) == 2
    assert all(not t.allow_prediction and t.fixture for t in tasks)
    tasks[0].fixture["results"].clear()
    assert fresh_acceptance_tasks()[0].fixture["results"]


def test_labels_from_independent_arithmetic():
    cases = {t.family: t for t in fresh_acceptance_tasks()}
    window = cases["inclusive_window"]
    assert window.expected == {
        "revenue": 60 + 42 + 36,
        "spend": 15 + 21 + 12,
        "roi": float(Fraction(60 + 42 + 36, 15 + 21 + 12)),
    }
    rows = selected_payload(["coefficients"], fixture=window.fixture, **window.evidence_window)[
        "results"
    ]["coefficients"]
    audio = [r for r in rows if r["Channel"] == "Audio_activity"]
    assert len(audio) == 2
    assert sum(Fraction(r["Revenue"]) for r in audio) == 102
    assert sum(Fraction(r["Spend"]) for r in audio) == 36
    assert cases["signed_reconciliation"].expected == {
        "media_total": 10 + 0,
        "non_media_excluding_overlap": 55 - 7,
        "overlap": 3,
        "reconstructed_model": 10 + 55 - 7 + 3,
    }
    assert cases["zero_spend_convention"].expected == {"revenue": 15 + 9, "spend": 0, "roi": 0}
    assert cases["diagnostic_threshold"].expected == {
        "passes_requested_rule": Fraction(1008, 1000) < Fraction(1005, 1000),
        "max_r_hat": 1.008,
    }


def test_labels_against_saved_contract_fields():
    cases = {t.family: t for t in fresh_acceptance_tasks()}
    marginal = cases["marginal_interval"]
    summary = marginal.fixture["results"]["mroi_summary"]
    row = summary["channels"][0]
    assert marginal.expected == {
        "median": row["mroi_median"],
        "lower": row["mroi_hdi_3"],
        "upper": row["mroi_hdi_97"],
        "hdi_prob": summary["hdi_prob"],
        "current_spend": row["current_spend"],
    }
    assert row["mroi_hdi_3"] < 0 < row["mroi_hdi_97"]
    missing = cases["absent_diagnostics"]
    assert selected_payload(["model_stats", "r_hat"], fixture=missing.fixture)["results"] == {}
    assert missing.expected == {"convergence": "unknown", "reason": "not_returned"}
    optional = cases["optional_history"]
    assert (
        selected_payload(["mroi_periods"], fixture=optional.fixture)["results"]["mroi_periods"]
        == optional.expected
    )
    identity = cases["colliding_identity"]
    mapping = {
        r["channel"]: r["activity_column"] for r in identity.fixture["results"]["channel_map"]
    }
    assert identity.expected == {
        "panel_identifier": mapping["Outdoor panel"],
        "digital_identifier": mapping["Outdoor digital"],
    }
    assert mapping["Outdoor panel"] != mapping["Outdoor digital"]


@pytest.mark.anyio
@pytest.mark.parametrize("task", fresh_acceptance_tasks(), ids=lambda task: task.id)
async def test_fresh_tasks_accept_each_sufficient_evidence_path(task):
    server = create_server("compact")
    for option in task.evidence_sets():
        dispatch = ResultSelectionDispatch(server, task)
        sections = option - {"verified_channel_identity"}
        _, error = await dispatch(
            "get_model_results",
            {
                "model_hash": "result-example",
                "sections": ",".join(sorted(sections)),
                **(task.evidence_window or {}),
            },
        )
        assert not error
        assert all(dispatch.grade(task.expected).values()), (task.id, option)


@pytest.mark.anyio
async def test_fresh_window_rejects_full_summary_and_missing_boundary_period():
    task = next(t for t in fresh_acceptance_tasks() if t.family == "inclusive_window")
    server = create_server("compact")
    for arguments in (
        {"sections": "channel_summary"},
        {"sections": "coefficients", "start": "2026-03-16", "end": "2026-03-16"},
    ):
        dispatch = ResultSelectionDispatch(server, task)
        _, error = await dispatch(
            "get_model_results", {"model_hash": "result-example", **arguments}
        )
        assert not error
        assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_fresh_zero_spend_accepts_complete_target_channel_periods_only():
    task = next(t for t in fresh_acceptance_tasks() if t.family == "zero_spend_convention")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    result, error = await dispatch(
        "get_model_results",
        {
            "model_hash": "result-example",
            "sections": "coefficients,channel_map",
            "channels": ["Partnership_activity"],
        },
    )
    assert not error
    assert len(result["results"]["coefficients"]) == 2
    assert all(dispatch.grade(task.expected).values())
    partial = ResultSelectionDispatch(create_server("compact"), task)
    _, error = await partial(
        "get_model_results",
        {
            "model_hash": "result-example",
            "sections": "coefficients,channel_map",
            "channels": ["Partnership_activity"],
            "start": "2026-06-05",
            "end": "2026-06-05",
        },
    )
    assert not error
    assert not partial.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_fresh_threshold_saved_maximum_is_sufficient_despite_success_label():
    task = next(t for t in fresh_acceptance_tasks() if t.family == "diagnostic_threshold")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    result, error = await dispatch(
        "get_model_results", {"model_hash": "result-example", "sections": "model_stats"}
    )
    assert not error
    stats = result["results"]["model_stats"][0]
    assert stats["Status"] == "success"
    assert float(stats["Output"]) >= 1.005
    assert all(dispatch.grade(task.expected).values())
    assert not dispatch.grade({"passes_requested_rule": True, "max_r_hat": 1.008})["facts"]


@pytest.mark.anyio
async def test_fresh_threshold_unrelated_section_cannot_support_correct_guess():
    task = next(t for t in fresh_acceptance_tasks() if t.family == "diagnostic_threshold")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    _, error = await dispatch(
        "get_model_results", {"model_hash": "result-example", "sections": "channel_summary"}
    )
    assert not error
    assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_fresh_window_accepts_complete_unwindowed_coefficients():
    task = next(t for t in fresh_acceptance_tasks() if t.family == "inclusive_window")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    _, error = await dispatch(
        "get_model_results", {"model_hash": "result-example", "sections": "coefficients"}
    )
    assert not error
    assert all(dispatch.grade(task.expected).values())


@pytest.mark.anyio
async def test_fresh_reconciliation_requires_mapping_not_names_or_configuration():
    task = next(t for t in fresh_acceptance_tasks() if t.family == "signed_reconciliation")
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    _, error = await dispatch(
        "get_model_results",
        {"model_hash": "result-example", "sections": "contributions,model_config"},
    )
    assert not error
    assert not dispatch.grade(task.expected)["required_evidence"]
