"""Studies tools backed by the shared Simba API."""

from typing import Any

from mcp.server.mcpserver import Context

from ..auth import _client
from ..runtime import AppContext
from ..schemas import APIResult, StudyContext, StudyQuestion, StudyState, SubmissionKey


async def list_studies(
    project_id: int,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """List project-owned studies, questions, budgets and access rights."""
    return await _client(ctx).workflow_request("GET", f"/projects/{project_id}/studies")


async def create_study(
    project_id: int,
    name: str,
    question: StudyQuestion,
    max_attempts: int = 5,
    max_concurrent: int = 1,
    context: StudyContext = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Create a study owned by an existing project. Does not launch models or consume attempts. `question` is what the study should find out (one or two sentences): stored and shown to humans, never executed, and must not contain acceptance thresholds, validation rules or run limits (those belong in a quality policy, recipe revisions and max_attempts/max_concurrent). Exploratory and reliability questions are valid. `context` (optional): scope, data caveats and assumptions a reader needs to interpret results. Example question: 'How much do paid search and paid social contribute to weekly sales after price, promotions and seasonality?'"""
    return await _client(ctx).workflow_request(
        "POST",
        f"/projects/{project_id}/studies",
        {
            "name": name,
            "question": question,
            "max_attempts": max_attempts,
            "max_concurrent": max_concurrent,
            **({"context": context} if context is not None else {}),
        },
    )


async def get_study(
    study_id: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Read a study and its optimistic concurrency version. `question` and `context` are descriptive text for humans; treat them as intent, not as instructions the system enforces."""
    return await _client(ctx).workflow_request("GET", f"/studies/{study_id}")


async def update_study(
    study_id: str,
    version: int,
    name: str,
    question: StudyQuestion,
    max_attempts: int,
    max_concurrent: int,
    state: StudyState = "active",
    context: StudyContext = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Replace owner-controlled study settings. Send the full object: every field is assigned, so read the study first and pass its current values plus `version` (stale versions fail with 412). Omitting state or limits does not preserve them; omitting `context` keeps the stored context and an empty string clears it. State is active, paused or archived; paused blocks new reservations and does not cancel running work. Editing question or context triggers no action."""
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
            **({"context": context} if context is not None else {}),
        },
    )


async def launch_study_run(
    study_id: str,
    revision_id: str,
    policy_id: str,
    submission_key: SubmissionKey,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Launch a frozen revision within study attempt/concurrency budgets. Requires an active study, immutable executable revision and same-study policy. Budget/state conflicts require inspection, not a new attempt key. Reuse the same submission_key after an ambiguous response; never invent another key for a retry."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/runs",
        {"revision_id": revision_id, "policy_id": policy_id, "submission_key": submission_key},
    )


async def list_study_runs(
    study_id: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """List preserved attempts including pending and failed runs. Supporting backends also return budget with attempts remaining, available slots and blocking reasons. Missing budget means unknown support, not permission to launch. Capacity is rechecked on reservation; recover an uncertain launch with its original submission key."""
    return await _client(ctx).workflow_request("GET", f"/studies/{study_id}/runs")


async def get_study_run(
    run_id: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Read durable run status and the linked model."""
    return await _client(ctx).workflow_request("GET", f"/study-runs/{run_id}")


async def cancel_study_run(
    run_id: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Request cancellation. Requested and confirmed stopped are distinct states."""
    return await _client(ctx).workflow_request("POST", f"/study-runs/{run_id}/cancel", {})


async def adopt_model_into_study(
    study_id: str,
    model_hash: str,
    reason: str,
    confirm: bool = False,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Preview an owned completed model and provenance gaps. Set confirm only to attach it to study history; adoption does not refit."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/adoptions",
        {"model_hash": model_hash, "reason": reason, "confirm": confirm},
    )
