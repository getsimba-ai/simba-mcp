"""Fixed tool catalogue profiles shared by registration and evaluation, never permissions."""

# Membership is intentional, including evidence and recovery dependencies across domains.
# Data scientists always get the canonical full catalogue, including future additions.
EVIDENCE = frozenset(
    [
        "get_workflow_guidance",
        "get_backend_capabilities",
        "list_projects",
        "list_models",
        "get_model",
        "get_model_status",
        "get_model_results",
        "get_contribution_groups",
        "list_studies",
        "get_study",
        "get_study_overview",
        "list_study_runs",
        "get_study_run",
        "list_study_recipes",
        "get_recipe_revision",
        "diff_recipe_revisions",
        "list_quality_policies",
        "get_quality_policy",
        "diff_quality_policies",
        "list_study_evaluations",
        "list_study_decisions",
        "get_study_champion",
        "get_study_prediction_access",
        "get_study_validation_resolutions",
        "compare_study_runs",
        "list_incrementality_tests",
        "get_incrementality_test",
        "list_campaigns",
        "get_campaign_report",
        "get_campaign_incrementality",
        "list_runs",
        "get_optimizer_results",
        "get_scenario_results",
        "get_scenario_template",
    ]
)
PROFILES = {
    "marketer": EVIDENCE
    | frozenset(
        [
            "run_optimizer",
            "run_scenario",
            "update_run",
            "set_run_pinned",
            "create_incrementality_test",
            "import_incrementality_tests",
            "set_campaign_mapping",
        ]
    ),
    "reviewer": EVIDENCE
    | frozenset(
        [
            "get_data_schema",
            "get_data_report",
            "get_recipe_revision_authoring",
            "evaluate_study_run",
            "assess_study_validation_pair",
            "declare_study_holdout_use",
            "recommend_study_run",
        ]
    ),
}
PROFILE_NAMES = ("full", "data_scientist", *PROFILES)


def _name(tool):
    return tool.__name__ if callable(tool) else tool.name


def select_tools(tools, role):
    """Filter actual definitions without copying contracts or mutating registration."""
    if role in ("full", "data_scientist"):
        return list(tools)
    if role not in PROFILES:
        raise ValueError(f"Unknown tool profile: {role}")
    names = PROFILES[role]
    missing = names - {_name(tool) for tool in tools}
    if missing:
        raise ValueError(f"Role references missing tools: {sorted(missing)}")
    return [tool for tool in tools if _name(tool) in names]
