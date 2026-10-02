"""Current complete jobs use real selected registrations and strict backend exchanges."""

import pytest

from simba_mcp.evaluation.role_workflows import role_workflows
from simba_mcp.evaluation.runner import run_case
from simba_mcp.server import create_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "role,workflow",
    [(role, workflow) for workflow in role_workflows() for role in workflow.roles],
    ids=lambda value: value if isinstance(value, str) else value.case.id,
)
async def test_current_role_jobs(role, workflow):
    trial = await run_case(workflow.case, mcp_server=create_server("compact", profile=role))
    assert trial.passed, trial.assertions
    assert trial.unintended_writes == 0
    assert trial.backend_attempts == sum(len(step.exchanges) for step in workflow.case.steps)


@pytest.mark.anyio
async def test_missing_reporting_dependency_fails_complete_job(monkeypatch):
    from simba_mcp.profiles import PROFILES

    monkeypatch.setitem(PROFILES, "marketer", PROFILES["marketer"] - {"get_upload"})
    workflow = next(item for item in role_workflows() if item.case.id == "role_actual_data")
    trial = await run_case(workflow.case, mcp_server=create_server(profile="marketer"))
    assert not trial.passed
    assert not trial.assertions["step_1_outcome"]


@pytest.mark.anyio
async def test_forbidden_request_is_detected_by_existing_runner():
    workflow = next(item for item in role_workflows() if item.case.id == "role_campaign_mapping")
    case = workflow.case.model_copy(deep=True)
    case.steps[0].exchanges[0].body = {"rows": [], "tolerance": 0.05}
    trial = await run_case(case, mcp_server=create_server(profile="marketer"))
    assert not trial.passed
    assert trial.unintended_writes == 1


@pytest.mark.anyio
@pytest.mark.parametrize("role", ["marketer", "reviewer"])
async def test_cross_role_authoring_stops_before_backend(role):
    from mcp.server.mcpserver.exceptions import ToolError

    workflow = next(item for item in role_workflows() if item.case.id == "create_mmm")
    with pytest.raises(ToolError):
        await create_server(profile=role).call_tool(
            workflow.case.steps[0].tool, workflow.case.steps[0].arguments
        )
