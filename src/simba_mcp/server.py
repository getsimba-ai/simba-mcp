"""Simba MCP composition and backwards-compatible public entrypoints."""

from mcp.server.mcpserver import MCPServer

from .auth import (
    _bearer_token,
    _client,
    _local_files_allowed,
    _local_files_denial_reason,
    set_http_mode,
)
from .runtime import MAX_REQUEST_BODY_BYTES, AppContext, _own_version, app_lifespan, create_app
from .tools import data, models, projects, quality, recipes, results, scenarios, studies
from .tools.data import MAX_UPLOAD_BYTES, get_data_schema, get_upload, list_uploads, upload_data
from .tools.models import (
    create_model,
    create_var_model,
    delete_model,
    get_contribution_groups,
    get_model,
    get_model_status,
    link_var_model,
    list_models,
    rename_model,
    save_model,
    set_contribution_groups,
    unlink_var_model,
    unsave_model,
)
from .tools.projects import create_project, list_projects, rename_project
from .tools.quality import (
    create_quality_policy,
    evaluate_study_run,
    list_quality_policies,
    list_study_decisions,
    list_study_evaluations,
    recommend_study_run,
)
from .tools.recipes import (
    create_study_recipe,
    get_recipe_revision,
    list_study_recipes,
    revise_study_recipe,
    validate_study_recipe,
)
from .tools.results import (
    _column_channel,
    _downsample,
    _filter_results,
    _norm_channel,
    get_model_results,
)
from .tools.scenarios import (
    get_optimizer_results,
    get_scenario_results,
    get_scenario_template,
    list_runs,
    run_optimizer,
    run_scenario,
    set_run_pinned,
    update_run,
)
from .tools.studies import (
    adopt_model_into_study,
    cancel_study_run,
    compare_study_runs,
    create_study,
    get_study,
    get_study_run,
    launch_study_run,
    list_studies,
    list_study_runs,
    update_study,
)

# Every argument keyword: the v2 constructor order is (name, title,
# description, instructions, ...) — a positional instructions lands in title.
mcp = MCPServer(
    name="Simba MMM",
    version=_own_version(),
    instructions=(
        "Simba is a Bayesian Marketing Mix Modeling (MMM) platform. "
        "Use these tools to upload marketing data, build MMM models, "
        "check fitting progress, retrieve results (channel ROI, contributions, "
        "model diagnostics), and run budget optimizations."
    ),
    lifespan=app_lifespan,
)

data.register(mcp)
projects.register(mcp)
models.register(mcp)
results.register(mcp)
scenarios.register(mcp)
studies.register(mcp)
recipes.register(mcp)
quality.register(mcp)


def _create_app():
    return create_app(mcp)


def __getattr__(name: str):
    """Lazy module-level attribute access to avoid creating the HTTP app in stdio mode."""
    if name == "app":
        global app
        app = _create_app()
        return app
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "MAX_REQUEST_BODY_BYTES",
    "MAX_UPLOAD_BYTES",
    "AppContext",
    "_bearer_token",
    "_client",
    "_column_channel",
    "_downsample",
    "_filter_results",
    "_local_files_allowed",
    "_local_files_denial_reason",
    "_norm_channel",
    "adopt_model_into_study",
    "app_lifespan",
    "cancel_study_run",
    "compare_study_runs",
    "create_model",
    "create_project",
    "create_quality_policy",
    "create_study",
    "create_study_recipe",
    "create_var_model",
    "delete_model",
    "evaluate_study_run",
    "get_contribution_groups",
    "get_data_schema",
    "get_model",
    "get_model_results",
    "get_model_status",
    "get_optimizer_results",
    "get_recipe_revision",
    "get_scenario_results",
    "get_scenario_template",
    "get_study",
    "get_study_run",
    "get_upload",
    "launch_study_run",
    "link_var_model",
    "list_models",
    "list_projects",
    "list_quality_policies",
    "list_runs",
    "list_studies",
    "list_study_decisions",
    "list_study_evaluations",
    "list_study_recipes",
    "list_study_runs",
    "list_uploads",
    "mcp",
    "recommend_study_run",
    "rename_model",
    "rename_project",
    "revise_study_recipe",
    "run_optimizer",
    "run_scenario",
    "save_model",
    "set_contribution_groups",
    "set_http_mode",
    "set_run_pinned",
    "unlink_var_model",
    "unsave_model",
    "update_run",
    "update_study",
    "upload_data",
    "validate_study_recipe",
]
