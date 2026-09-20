"""Quality tools backed by the shared Simba API."""

from typing import Any

from mcp.server.mcpserver import Context

from ..auth import _client
from ..runtime import AppContext
from ..schemas import APIResult, ExternalEvidence, QualityCheck


async def list_quality_policies(
    study_id: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Read immutable quality policies for the study."""
    return await _client(ctx).workflow_request("GET", f"/studies/{study_id}/quality-policies")


async def create_quality_policy(
    study_id: str,
    name: str,
    rationale: str,
    checks: list[QualityCheck],
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Save project-specific checks. Built-in checks have metric (r_hat_max, mae, rmse, wape), maximum and required. Custom numeric checks use metric custom:<slug>, name, units, operator (lte/gte/between), applicable minimum/maximum and required. Boolean checks use kind=boolean, operator=equals and expected=true/false. Manual checks use kind=manual, equals, expected=true; agents can define these but cannot submit manual sign-off. Custom bounds may be negative. WAPE is a fraction. No default thresholds are assumed. Declare at least one required check, use each metric once, and set maximum R-hat at least 1. The backend validates policy rules."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/quality-policies",
        {"name": name, "rationale": rationale, "checks": checks},
    )


async def evaluate_study_run(
    run_id: str,
    policy_id: str,
    expected_basis_hash: str | None = None,
    external_evidence: list[ExternalEvidence] | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Save an immutable assessment. First evaluate without external_evidence to obtain report.basis_hash; then calculate custom metrics from outputs and submit finite numeric or strict boolean values, method and source reference with that expected_basis_hash. The server applies the saved rule; stale model evidence is rejected. External calculations are submitter-reported, not verified. Each submission is complete: omitted custom values stay unevaluated. Manual sign-off requires a signed-in reviewer and is rejected for API keys. No automatic champion promotion. Built-in errors are fitted-window, not holdout; VAR remains unsupported."""
    payload: dict[str, Any] = {"policy_id": policy_id}
    if expected_basis_hash is not None:
        payload["expected_basis_hash"] = expected_basis_hash
    if external_evidence is not None:
        payload["external_evidence"] = external_evidence
    return await _client(ctx).workflow_request("POST", f"/study-runs/{run_id}/evaluations", payload)


async def list_study_evaluations(
    run_id: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Read preserved quality reports and evidence hashes."""
    return await _client(ctx).workflow_request("GET", f"/study-runs/{run_id}/evaluations")


async def list_study_decisions(
    study_id: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Read analyst decisions and agent recommendations."""
    return await _client(ctx).workflow_request("GET", f"/studies/{study_id}/decisions")


async def recommend_study_run(
    study_id: str,
    run_id: str,
    evaluation_id: str,
    reason: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Record a recommendation with evidence. This does not accept or promote a model; analyst acceptance happens in the frontend."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/decisions",
        {"run_id": run_id, "evaluation_id": evaluation_id, "action": "recommend", "reason": reason},
    )


async def compare_study_runs(
    study_id: str,
    run_ids: list[str],
    policy_id: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Compare 2-20 candidates against one quality policy. Different datasets are flagged, not ranked. Does not fit or promote models."""
    return await _client(ctx).workflow_request(
        "POST", f"/studies/{study_id}/comparisons", {"run_ids": run_ids, "policy_id": policy_id}
    )
