"""Independent arithmetic and evidence-path verification for fresh specifications."""

from datetime import UTC, datetime
from fractions import Fraction

import pytest

from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
from simba_mcp.evaluation.result_acceptance import acceptance_tasks
from simba_mcp.server import create_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_independent_arithmetic_oracles():
    tasks = {t.id: t for t in acceptance_tasks()}
    task = tasks["acceptance_a"]
    rows = task.fixture["results"]["coefficients"]
    selected = [
        r
        for r in rows
        if "2026-03-10"
        <= datetime.fromtimestamp(r["Date"] / 1000, tz=UTC).date().isoformat()
        <= "2026-03-24"
    ]
    assert len(selected) == 9
    revenue = sum(Fraction(r["Revenue"]) for r in selected)
    spend = sum(Fraction(r["Spend"]) for r in selected)
    assert (revenue, spend) == (460, 180)
    assert float(round(revenue / spend, 6)) == task.expected["roi"]
    assert sum(Fraction(r["Revenue"], r["Spend"]) for r in selected) / 9 != revenue / spend
    all_revenue = sum(r["Revenue"] for r in rows)
    assert all_revenue == tasks["acceptance_i"].expected["revenue"]
    for summary in task.fixture["results"]["channel_summary"]:
        channel_rows = [r for r in rows if r["Channel"] == summary["Channel"]]
        assert sum(r["Revenue"] for r in channel_rows) == summary["Revenue"]
        assert sum(r["Spend"] for r in channel_rows) == summary["Spend"]
    row = tasks["acceptance_f"].fixture["results"]["contributions"][0]
    assert sum(v for k, v in row.items() if k not in ("Date", "Model")) == 130 == row["Model"]
    diagnostics = tasks["acceptance_c"].fixture["results"]["r_hat"]
    breaches = [r for r in diagnostics if Fraction(str(r["R_hat"])) > Fraction(101, 100)]
    assert len(breaches) == 1
    assert breaches[0]["Parameter"] == tasks["acceptance_c"].expected["breaching_parameter"]


@pytest.mark.anyio
@pytest.mark.parametrize("task", acceptance_tasks(), ids=lambda t: t.id)
async def test_all_ten_have_executable_sufficient_evidence(task):
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    _, error = await dispatch(
        "get_model_results",
        {
            "model_hash": "result-example",
            "sections": ",".join(sorted(task.required_sections)),
            **(task.evidence_window or {}),
        },
    )
    assert not error
    assert dispatch.grade(task.expected)["required_evidence"]
    assert dispatch.grade(task.expected)["facts"]


@pytest.mark.anyio
async def test_window_alternative_is_complete_period_evidence():
    task = acceptance_tasks()[0]
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    await dispatch(
        "get_model_results", {"model_hash": "result-example", "sections": "coefficients"}
    )
    assert dispatch.grade(task.expected)["required_evidence"]
    wrong = ResultSelectionDispatch(create_server("compact"), task)
    await wrong(
        "get_model_results", {"model_hash": "result-example", "sections": "channel_summary"}
    )
    assert not wrong.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
async def test_recovery_has_no_partial_evidence_and_keeps_error():
    task = acceptance_tasks()[-1]
    dispatch = ResultSelectionDispatch(create_server("compact"), task)
    _, error = await dispatch("get_model_results", {"model_hash": "result-example"})
    assert error
    assert not dispatch.grade(task.expected)["required_evidence"]
    _, error = await dispatch(
        "get_model_results", {"model_hash": "result-example", "sections": "mroi_summary"}
    )
    assert not error
    assert dispatch.errors == 1
    assert dispatch.grade(task.expected)["required_evidence"]
    assert dispatch.grade(task.expected)["no_errors"]
