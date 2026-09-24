"""Quality tools backed by the shared Simba API."""

from typing import Any, Literal

from mcp.server.mcpserver import Context

from ..auth import _client, _page
from ..runtime import AppContext
from ..schemas import APIResult, ExternalEvidence, QualityCheck, ValidationProtocolSpec


async def list_quality_policies(
    study_id: str,
    limit: int | None = None,
    cursor: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Read immutable quality policies for the study. Each row carries the full specification plus identity: content_hash (the stored row, including name and rationale), rules_hash (the rules alone: checks sorted by metric plus the protocol, so two policies with the same rules_hash apply the same rules whatever they are called), is_newest, derived_from, created_at, retired_at, usage counts (runs_launched, evaluations, resolutions, champion_acceptances) and checks_summary / protocol_summary. Newest is information, not a recommendation: choose policy_id explicitly. Retired policies stay listed for history but are refused for new launches, assessments and pair reviews. Deleting a policy is possible only for a policy nothing references and only from the signed-in project owner UI, never through this API key."""
    return await _client(ctx).workflow_request(
        "GET", f"/studies/{study_id}/quality-policies", params=_page(limit, cursor)
    )


async def get_quality_policy(
    study_id: str,
    policy_id: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Read one immutable policy in full: specification, content_hash (identity of the stored row), rules_hash (identity of the rules alone, the value evidence carry-forward compares), is_newest, derived_from (null until a policy is created from another), checks_summary (builtin / custom_numeric / boolean / manual / diagnostic, required, advisory, cap) and protocol_summary, plus usage with the ids of every run, assessment, resolution and Champion acceptance that references it. Shared viewers can read; nothing is written."""
    return await _client(ctx).workflow_request(
        "GET", f"/studies/{study_id}/quality-policies/{policy_id}"
    )


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


async def retire_quality_policy(
    study_id: str,
    policy_id: str,
    retired: bool = True,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Retire (retired=true) or restore (retired=false) a saved policy without changing it. A retired policy is refused for new launches, new assessments and new pair-review resolutions, stops counting as the newest policy, and stays readable in every run, assessment, pair review, comparison and Champion record that already names it. Idempotent; the backend records each change. Requires create:models on the study's project. Nothing is deleted: removal of an unreferenced policy is an owner-only frontend action."""
    return await _client(ctx).workflow_request(
        "PATCH", f"/studies/{study_id}/quality-policies/{policy_id}", {"retired": retired}
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
    limit: int | None = None,
    cursor: str | None = None,
    expand: list[Literal["report"]] | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """List preserved assessments as summaries: id, policy_id, policy_name, status, basis_hash, evidence_hash, created_at. Pass expand=["report"] for the full per-check report; serving available prediction reports appends access audit events, summaries do not. Paging is opt-in: pass limit (1-200) to receive a page and next_cursor; send that cursor back unchanged for the next page; null next_cursor means the end. Without limit every row is returned. Rows you cannot see are simply absent; no totals are promised."""
    return await _client(ctx).workflow_request(
        "GET", f"/study-runs/{run_id}/evaluations", params=_page(limit, cursor, expand)
    )


async def list_study_decisions(
    study_id: str,
    limit: int | None = None,
    cursor: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Read analyst decisions and agent recommendations. Paging is opt-in: pass limit (1-200) to receive a page and next_cursor; send that cursor back unchanged for the next page; null next_cursor means the end. Without limit every row is returned. Rows you cannot see are simply absent; no totals are promised."""
    return await _client(ctx).workflow_request(
        "GET", f"/studies/{study_id}/decisions", params=_page(limit, cursor)
    )


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
    """Compare 2-20 candidates against one quality policy. Each row carries a basis record (family, dataset and costs hashes, outcome column, units, training window, output kind, prediction window, evidence freshness) and a per-dimension compatibility against the first row; rows are comparable only when family, dataset, outcome, units, window and output kind all match, and incompatible rows are returned with the differing dimension in blockers and are never ranked. This answers predictive ranking only: sensitivity agreement is not computed, analyst acceptance lives in decisions, and business validity is a human review. Serving prediction evidence appends access audit events. Does not fit or promote models."""
    return await _client(ctx).workflow_request(
        "POST", f"/studies/{study_id}/comparisons", {"run_ids": run_ids, "policy_id": policy_id}
    )


async def get_study_champion(study_id: str, ctx: Context[AppContext, Any] = None) -> APIResult:
    """Read incumbent, eligibility blockers, accepted candidates and immutable champion history. Stale champions retain their historical role with review_required. Reported holdout use that informed a candidate revision blocks that revision pending fresh validation; holdout_use lists the declaration IDs. Ordinary viewing does not block. Current analyst-reviewed validation resolutions can clear the exact run acceptance; changed evidence or revoked review reblocks it. Recorded revision ancestry inherits influence. Validation references are reviewer-declared; decision_grade_ready is false until independently qualified. Selection/replacement/revocation require an owner frontend session; MCP cannot promote models."""
    return await _client(ctx).workflow_request("GET", f"/studies/{study_id}/champion")


async def assess_study_validation_pair(
    study_id: str,
    full_run_id: str,
    validation_run_id: str,
    policy_id: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Assess a validation pair and append a prediction-access audit event when evidence is available. Checks distinct completed MMM runs launched under the declared protocol, frozen inputs/settings/runtime, configured sampling, saved R-hat, declared prediction windows/WAPE and date coverage. Returns blockers and an evidence hash; does not fit, accept or promote. Includes saved retained chain/draw, ESS and divergence records when available, with null for older models. Optional prelaunch retained_sampling limits require complete native records and check chain/draw minima, bulk/tail ESS minima and maximum divergences; otherwise sampling_qualification is not_declared. Optional require_policy_review checks current signed-in analyst acceptance of each latest same-policy assessment, including freshness and rejection blockers. The holdout_provenance report distinguishes missing evidence, blocked version 1 full-input preprocessing and version 2 training-only preprocessing requiring further provenance review. The prior_provenance report checks recorded automatic-prior source dates and frozen input hashes; missing legacy/uploaded provenance remains unavailable, and recorded inputs after the declared training end are blocked. fresh_validation provides replacement-window preflight for influence reports naming the full-model revision: later windows, replacement policy chronology, recorded prior exposure, retained diagnostics and provenance/review requirements. It never clears champion blocks. External business calculations and untouched holdout history remain unverified; decision_grade_ready stays false."""
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


async def declare_study_holdout_use(
    run_id: str,
    declaration_id: str,
    source_access_id: str,
    disposition: Literal["review_only", "informed_revision", "uncertain"],
    reason: str,
    affected_revision_id: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Append a submitter-reported evidence-use declaration using project-owner credentials and create:models. Read get_study_prediction_access first and reference an access event from this run. Use a fresh UUID declaration_id and reuse it unchanged on retry. informed_revision requires a published affected revision in the same study; other dispositions omit it. Reason must explain actual use. Reported revision influence requires fresh validation for affected revisions; later review-only notes cannot erase it. Does not certify independence, accept or promote a model. API submissions remain identified as reported declarations."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/study-runs/{run_id}/holdout-use",
        {
            "id": declaration_id,
            "source_access_id": source_access_id,
            "disposition": disposition,
            "reason": reason,
            "affected_revision_id": affected_revision_id,
        },
    )


async def get_study_validation_resolutions(
    study_id: str, ctx: Context[AppContext, Any] = None
) -> APIResult:
    """Read analyst validation resolutions and revocations, including current/stale/revoked status re-evaluated against exact evidence. API keys cannot supply human independence sign-off or revoke it; use the signed-in owner UI. No audit serving event is added and no model is fitted or promoted."""
    return await _client(ctx).workflow_request("GET", f"/studies/{study_id}/validation-resolutions")
