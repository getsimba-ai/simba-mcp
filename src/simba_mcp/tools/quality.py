"""Quality tools backed by the shared Simba API."""

from typing import Any

from mcp.server.mcpserver import Context

from ..auth import _client
from ..runtime import AppContext
from ..schemas import APIResult, ExternalEvidence, QualityCheck, ValidationProtocolSpec


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
    validation_protocol: ValidationProtocolSpec | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Save project-specific checks. Built-in checks have metric (r_hat_max, mae, rmse, wape, prediction_mae, prediction_rmse, prediction_wape), maximum and required. Custom numeric checks use metric custom:<slug>, name, units, operator (lte/gte/between), applicable minimum/maximum and required. Boolean checks use kind=boolean, operator=equals and expected=true/false. Manual checks use kind=manual, equals, expected=true; agents can define these but cannot submit manual sign-off. Custom bounds may be negative. WAPE is a fraction. Prediction-window checks require saved finite actuals/predictions at unique dates after the saved training window; this does not certify untouched holdout provenance. No default thresholds are assumed. Declare at least one required check, use each metric once, and set maximum R-hat at least 1. Optional validation_protocol declares a temporal holdout split, configured sampling minima, R-hat and prediction WAPE limits before both runs launch under this policy. The backend validates policy rules."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/quality-policies",
        {
            "name": name,
            "rationale": rationale,
            "checks": checks,
            **(
                {"validation_protocol": validation_protocol}
                if validation_protocol is not None
                else {}
            ),
        },
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
    """Read preserved quality reports and evidence hashes. Serving available prediction reports appends access audit events."""
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
    """Compare 2-20 candidates against one quality policy. Serving prediction evidence appends access audit events. Different datasets are flagged, not ranked. Does not fit or promote models."""
    return await _client(ctx).workflow_request(
        "POST", f"/studies/{study_id}/comparisons", {"run_ids": run_ids, "policy_id": policy_id}
    )


async def get_study_champion(study_id: str, ctx: Context[AppContext, Any] = None) -> APIResult:
    """Read incumbent, eligibility blockers, accepted candidates and immutable champion history. Stale champions retain their historical role with review_required. Validation references are reviewer-declared; decision_grade_ready is false until independently qualified. Selection/replacement/revocation require an owner frontend session; MCP cannot promote models."""
    return await _client(ctx).workflow_request("GET", f"/studies/{study_id}/champion")


async def assess_study_validation_pair(
    study_id: str,
    full_run_id: str,
    validation_run_id: str,
    policy_id: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Assess a validation pair and append a prediction-access audit event when evidence is available. Checks distinct completed MMM runs launched under the declared protocol, frozen inputs/settings/runtime, configured sampling, saved R-hat, declared prediction windows/WAPE and date coverage. Returns blockers and an evidence hash; does not fit, accept or promote. Includes saved retained chain/draw, ESS and divergence records when available, with null for older models. Optional prelaunch retained_sampling limits require complete native records and check chain/draw minima, bulk/tail ESS minima and maximum divergences; otherwise sampling_qualification is not_declared. Optional require_policy_review checks current signed-in analyst acceptance of each latest same-policy assessment, including freshness and rejection blockers. The holdout_provenance report distinguishes missing evidence, blocked version 1 full-input preprocessing and version 2 training-only preprocessing requiring further provenance review. The prior_provenance report checks recorded automatic-prior source dates and frozen input hashes; missing legacy/uploaded provenance remains unavailable, and recorded inputs after the declared training end are blocked. External business calculations and untouched holdout history remain unverified; decision_grade_ready stays false."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/validation-pairs",
        {
            "full_run_id": full_run_id,
            "validation_run_id": validation_run_id,
            "policy_id": policy_id,
        },
    )


async def get_study_prediction_access(
    run_id: str, ctx: Context[AppContext, Any] = None
) -> APIResult:
    """Read partial prediction-access history for this run and matching recorded dataset/windows in this study. Does not expose predictions or add access events. Earlier activity, other result routes and offline work are not covered; absence never proves untouched holdout status. Repeated access does not prove retuning."""
    return await _client(ctx).workflow_request("GET", f"/study-runs/{run_id}/prediction-access")
