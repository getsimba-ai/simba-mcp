"""Explicit tool effects. MCP annotations are hints, never authorization."""

from mcp.types import ToolAnnotations

READ_ONLY = frozenset(
    [
        "get_recipe_draft",
        "get_recipe_draft_template",
        "get_recipe_revision_authoring",
        "list_recipe_drafts",
        "get_data_schema",
        "list_uploads",
        "get_upload",
        "list_models",
        "get_model",
        "get_model_status",
        "list_projects",
        "get_contribution_groups",
        "get_optimizer_results",
        "get_scenario_template",
        "get_scenario_results",
        "list_runs",
        "list_studies",
        "get_study",
        "list_study_recipes",
        "get_recipe_revision",
        "validate_study_recipe",
        "list_study_runs",
        "get_study_run",
        "list_quality_policies",
        "list_study_decisions",
        "get_study_champion",
        "get_study_prediction_access",
        "get_backend_capabilities",
    ]
)
# Any operation that can replace/remove existing state is conservative/destructive.
DESTRUCTIVE = frozenset(
    [
        "update_recipe_draft",
        "delete_model",
        "unsave_model",
        "save_model",
        "rename_model",
        "rename_project",
        "link_var_model",
        "unlink_var_model",
        "set_contribution_groups",
        "update_run",
        "set_run_pinned",
        "update_study",
        "cancel_study_run",
    ]
)
IDEMPOTENT_WRITES = frozenset(
    [
        "create_recipe_draft",
        "publish_recipe_draft",
        "update_recipe_draft",
        "launch_study_run",
        "delete_model",
        "rename_model",
        "rename_project",
        "set_run_pinned",
        "set_contribution_groups",
        "unlink_var_model",
    ]
)
ADDITIVE_WRITES = frozenset(
    [
        "create_recipe_draft",
        "publish_recipe_draft",
        "upload_data",
        "create_model",
        "create_var_model",
        "create_project",
        "run_optimizer",
        "run_scenario",
        "create_study",
        "create_study_recipe",
        "revise_study_recipe",
        "launch_study_run",
        "create_quality_policy",
        "evaluate_study_run",
        "get_model_results",
        "list_study_evaluations",
        "assess_study_validation_pair",
        "compare_study_runs",
        "recommend_study_run",
        "adopt_model_into_study",
    ]
)


def annotations_for(name: str) -> ToolAnnotations:
    if name not in READ_ONLY | DESTRUCTIVE | ADDITIVE_WRITES:
        raise ValueError(f"Classify tool effects before registering {name}")
    return ToolAnnotations(
        read_only_hint=name in READ_ONLY,
        destructive_hint=name in DESTRUCTIVE,
        idempotent_hint=name in READ_ONLY | IDEMPOTENT_WRITES,
        open_world_hint=True,
    )
