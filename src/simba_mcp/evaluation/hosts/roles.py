"""Task assignments; frozen paid comparisons stay separate from current role jobs."""

ROLE_CASES = {
    "marketer": (
        "analyse_model",
        "optimiser_setup",
        "study_review",
        "cross_domain",
        "planning_lifecycle",
        "failed_scenario",
    ),
    "reviewer": (
        "analyse_model",
        "study_review",
        "cross_domain",
        "incompatible_candidates",
        "evidence_recommendation",
    ),
}


def current_role_cases():
    """Current synthetic jobs, without silently extending historical provider trials."""
    from ..role_workflows import role_workflows

    return {
        role: tuple(item.case.id for item in role_workflows() if role in item.roles)
        for role in ("marketer", "reviewer", "data_scientist", "full")
    }
