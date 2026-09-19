"""Quality tools backed by the Simba API."""

from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from ..auth import _client
from ..runtime import AppContext


async def list_quality_policies(
    study_id: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Read immutable quality policies for the study."""
    return await _client(ctx).workflow_request("GET", f"/studies/{study_id}/quality-policies")


async def create_quality_policy(
    study_id: str,
    name: str,
    rationale: str,
    checks: list[dict],
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Save project-specific checks. Each check has metric (r_hat_max, mae, rmse, wape), maximum and required. WAPE is a fraction. No default thresholds are assumed."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/quality-policies",
        {"name": name, "rationale": rationale, "checks": checks},
    )


async def evaluate_study_run(
    run_id: str,
    policy_id: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Save a quality report from existing evidence. Missing evidence never passes. Current predictive metrics cover the fitted window, not holdout."""
    return await _client(ctx).workflow_request(
        "POST", f"/study-runs/{run_id}/evaluations", {"policy_id": policy_id}
    )


async def list_study_evaluations(
    run_id: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Read preserved quality reports and evidence hashes."""
    return await _client(ctx).workflow_request("GET", f"/study-runs/{run_id}/evaluations")


async def list_study_decisions(
    study_id: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Read analyst decisions and agent recommendations."""
    return await _client(ctx).workflow_request("GET", f"/studies/{study_id}/decisions")


async def recommend_study_run(
    study_id: str,
    run_id: str,
    evaluation_id: str,
    reason: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Record a recommendation with evidence. This does not accept or promote a model; analyst acceptance happens in the frontend."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/decisions",
        {"run_id": run_id, "evaluation_id": evaluation_id, "action": "recommend", "reason": reason},
    )


def register(mcp: MCPServer) -> None:
    mcp.tool()(list_quality_policies)
    mcp.tool()(create_quality_policy)
    mcp.tool()(evaluate_study_run)
    mcp.tool()(list_study_evaluations)
    mcp.tool()(list_study_decisions)
    mcp.tool()(recommend_study_run)
