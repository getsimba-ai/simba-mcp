"""Prospective repairs motivated by independent complete-task audit defects."""

from pathlib import Path

import pytest

from simba_mcp.evaluation.contracts import Case
from simba_mcp.evaluation.hosts.result_grading import semantic_facts
from simba_mcp.evaluation.hosts.result_selection import ResultTask
from simba_mcp.evaluation.hosts.scenarios import SyntheticDispatch
from simba_mcp.evaluation.hosts.workflow_packet import WorkflowEntry, load_workflow_packet
from simba_mcp.evaluation.runner import run_case
from simba_mcp.server import create_server

PACKET = Path(__file__).parents[2] / "docs/evaluations/packets/routing-task-selection-v2.json"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_repaired_workflows_execute_real_mcp_and_preserve_24_task_scope():
    packet = load_workflow_packet(PACKET)
    assert len(packet.triples()) == 24
    for entry in packet.document.tasks:
        if isinstance(entry, WorkflowEntry):
            trial = await run_case(entry.contract)
            assert trial.passed, (entry.contract.id, trial.assertions)
            assert trial.unintended_writes == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("task_id", "order"),
    [
        ("role_campaign_facts", [1, 2, 0]),
        ("role_campaign_facts", [2, 1]),
        ("role_native_results", [1, 0]),
        ("role_native_results", [2]),
        ("role_saved_allocation", [1, 0]),
        ("role_saved_allocation", [3, 2]),
        ("role_saved_allocation", [2, 1]),
        ("role_actual_data", [0, 3]),
    ],
)
async def test_sufficient_alternative_evidence_is_accepted(task_id, order):
    case = next(case for case, _, _ in load_workflow_packet(PACKET).triples() if case.id == task_id)
    dispatch = SyntheticDispatch(create_server("compact"), case)
    for index in order:
        step = case.steps[index]
        _, error = await dispatch(step.tool, step.arguments)
        assert not error, (task_id, index, dispatch.trials[-1].assertions)
    assert dispatch.evidence_satisfied
    assert dispatch.errors == dispatch.unintended_writes == 0
    # A repeated safe snapshot read changes measurements, not evidence coverage.
    step = case.steps[order[0]]
    completed = dispatch.completed
    _, error = await dispatch(step.tool, step.arguments)
    assert not error and dispatch.completed == completed


@pytest.mark.anyio
async def test_result_section_order_is_equivalent_but_extra_sections_are_not():
    case = next(
        case
        for case, _, _ in load_workflow_packet(PACKET).triples()
        if case.id == "role_native_results"
    )
    dispatch = SyntheticDispatch(create_server("compact"), case)
    args = dict(case.steps[2].arguments)
    args["sections"] = ",".join(reversed(args["sections"].split(",")))
    _, error = await dispatch("get_model_results", args)
    assert not error and dispatch.evidence_satisfied
    args["sections"] += ",prediction_window"
    _, error = await dispatch("get_model_results", args)
    assert error and dispatch.unauthorised_reads == 1


@pytest.mark.anyio
async def test_result_sections_can_be_read_in_sufficient_subsets():
    case = next(
        case
        for case, _, _ in load_workflow_packet(PACKET).triples()
        if case.id == "role_native_results"
    )
    dispatch = SyntheticDispatch(create_server("compact"), case)
    for sections in ("response_curves,channel_map", "contributions,model_config"):
        result, error = await dispatch(
            "get_model_results",
            {
                "model_hash": "model-example",
                "sections": sections,
            },
        )
        assert not error and set(result) == set(sections.split(","))
        if sections.startswith("response"):
            assert not dispatch.evidence_satisfied
    assert dispatch.evidence_satisfied and dispatch.errors == 0


@pytest.mark.anyio
async def test_campaign_metrics_order_does_not_change_authorised_evidence():
    case = next(
        case
        for case, _, _ in load_workflow_packet(PACKET).triples()
        if case.id == "role_campaign_facts"
    )
    dispatch = SyntheticDispatch(create_server("compact"), case)
    for index in (1, 2):
        step = case.steps[index]
        args = dict(step.arguments)
        if "metrics" in args:
            args["metrics"] = list(reversed(args["metrics"]))
        _, error = await dispatch(step.tool, args)
        assert not error
    assert dispatch.evidence_satisfied


@pytest.mark.anyio
async def test_stateful_authorised_write_order_cannot_be_relaxed_or_replayed():
    case = next(
        case
        for case, _, _ in load_workflow_packet(PACKET).triples()
        if case.id == "role_mapping_uncertain"
    )
    with pytest.raises(ValueError, match="independent GET"):
        Case.model_validate({**case.model_dump(), "execution": "snapshot_evidence"})
    dispatch = SyntheticDispatch(create_server("compact"), case)
    for step in case.steps:
        await dispatch(step.tool, step.arguments)
    assert dispatch.evidence_satisfied and dispatch.unintended_writes == 0
    await dispatch(case.steps[0].tool, case.steps[0].arguments)
    assert dispatch.unintended_writes == 1


@pytest.mark.anyio
async def test_unexpected_safe_result_read_is_not_misreported_as_a_write():
    case = next(
        case
        for case, _, _ in load_workflow_packet(PACKET).triples()
        if case.id == "routing_var_failure"
    )
    dispatch = SyntheticDispatch(create_server("compact"), case)
    _, error = await dispatch(
        "get_model_results", {"model_hash": "var-example", "sections": "channel_summary"}
    )
    assert error and dispatch.errors == 1 and dispatch.unintended_writes == 0
    assert dispatch.unauthorised_reads == 0
    _, error = await dispatch(
        "get_model_results", {"model_hash": "var-example", "sections": "prediction_window"}
    )
    assert error and dispatch.unauthorised_reads == 1


def test_task_level_answers_include_comparison_and_independently_declared_absence():
    entries = {entry.contract.id: entry for entry in load_workflow_packet(PACKET).document.tasks}
    allocation = entries["role_saved_allocation"].expected
    assert set(allocation["runs"]) == {"optim-one", "optim-two"}
    assert allocation["spend_delta"] == 20
    assert allocation["decision_revenue_delta"] == 40
    assert allocation["fitted_revenue_delta"] == 60
    old = entries["result_old_artifact"]
    assert old.contract.fixture["results"]["mroi_periods"] == old.expected
    task = ResultTask(
        "nested_evidence", "saved evidence", frozenset(), {"result": {"accepted": False}}
    )
    assert not semantic_facts(task, {"result": {"accepted": 0}}, set(), grader_version=20)
    assert not semantic_facts(
        task,
        {"result": {"accepted": False, "claim": "scientifically accepted"}},
        set(),
        grader_version=20,
    )
