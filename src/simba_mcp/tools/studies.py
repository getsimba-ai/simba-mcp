"""Studies tools backed by the shared Simba API."""

from typing import Any

from mcp.server.mcpserver import Context

from ..auth import _client
from ..runtime import AppContext


async def list_studies(
    project_id: int,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """List project-owned studies, questions, budgets and access rights."""
    return await _client(ctx).workflow_request("GET", f"/projects/{project_id}/studies")


async def create_study(
    project_id: int,
    name: str,
    question: str,
    max_attempts: int = 5,
    max_concurrent: int = 1,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Create a study owned by an existing project. Does not launch models."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/projects/{project_id}/studies",
        {
            "name": name,
            "question": question,
            "max_attempts": max_attempts,
            "max_concurrent": max_concurrent,
        },
    )


async def get_study(
    study_id: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Read a study and its optimistic concurrency version."""
    return await _client(ctx).workflow_request("GET", f"/studies/{study_id}")


async def update_study(
    study_id: str,
    version: int,
    name: str,
    question: str,
    max_attempts: int,
    max_concurrent: int,
    state: str = "active",
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Update owner-controlled study settings. State is active, paused or archived. Stale versions fail."""
    return await _client(ctx).workflow_request(
        "PATCH",
        f"/studies/{study_id}",
        {
            "version": version,
            "name": name,
            "question": question,
            "max_attempts": max_attempts,
            "max_concurrent": max_concurrent,
            "state": state,
        },
    )


async def launch_study_run(
    study_id: str,
    revision_id: str,
    policy_id: str,
    submission_key: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Launch a frozen revision within study budget. Reuse the same submission_key after an ambiguous response; never invent another key for a retry."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/runs",
        {"revision_id": revision_id, "policy_id": policy_id, "submission_key": submission_key},
    )


async def list_study_runs(
    study_id: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """List preserved attempts including pending and failed runs."""
    return await _client(ctx).workflow_request("GET", f"/studies/{study_id}/runs")


async def get_study_run(
    run_id: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Read durable run status and the linked model."""
    return await _client(ctx).workflow_request("GET", f"/study-runs/{run_id}")


async def cancel_study_run(
    run_id: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Request cancellation. Requested and confirmed stopped are distinct states."""
    return await _client(ctx).workflow_request("POST", f"/study-runs/{run_id}/cancel", {})


async def adopt_model_into_study(
    study_id: str,
    model_hash: str,
    reason: str,
    confirm: bool = False,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Preview an owned completed model and provenance gaps. Set confirm only to attach it to study history; adoption does not refit."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/adoptions",
        {"model_hash": model_hash, "reason": reason, "confirm": confirm},
    )
