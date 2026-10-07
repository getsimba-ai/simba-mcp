"""Public selection packet contract and real MCP execution against synthetic HTTP."""

from pathlib import Path

import pytest

from simba_mcp.evaluation.hosts.workflow_packet import WorkflowEntry, load_workflow_packet
from simba_mcp.evaluation.runner import run_case

PACKET = Path(__file__).parents[2] / "docs/evaluations/packets/routing-task-selection-v1.json"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_packet_has_24_distinct_tasks_and_all_eight_domains_without_acceptance():
    packet = load_workflow_packet(PACKET)
    assert len(packet.triples()) == 24
    assert len({case.id for case, _, _ in packet.triples()}) == 24
    families = {
        entry.family if isinstance(entry, WorkflowEntry) else entry.contract.family
        for entry in packet.document.tasks
    }
    assert families == {
        "mmm",
        "results",
        "priors",
        "optimiser",
        "studies",
        "var",
        "campaigns",
        "reporting",
        "mixed_or_unclear",
    }
    assert packet.freeze()["acceptance"] is False
    packet.verify()


@pytest.mark.anyio
async def test_all_workflow_contracts_execute_against_real_mcp_without_unintended_writes():
    for entry in load_workflow_packet(PACKET).document.tasks:
        if isinstance(entry, WorkflowEntry):
            trial = await run_case(entry.contract)
            assert trial.passed, (entry.contract.id, trial.assertions)
            assert trial.unintended_writes == 0
