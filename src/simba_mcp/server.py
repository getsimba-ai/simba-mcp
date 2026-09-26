"""Simba MCP composition and registration. Backend services own durable state."""

import functools
import json

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent

from . import runtime
from .auth import _bearer_token, _client, _local_files_allowed
from .metadata import annotations_for
from .runtime import (
    MAX_REQUEST_BODY_BYTES,
    MAX_UPLOAD_BYTES,
    AppContext,
    app_lifespan,
    set_http_mode,
)
from .tools.data import (
    get_backend_capabilities,
    get_data_schema,
    get_upload,
    list_pipeline_versions,
    list_pipelines,
    list_uploads,
    upload_data,
)
from .tools.drafts import (
    create_recipe_draft,
    get_recipe_draft,
    get_recipe_draft_template,
    get_recipe_revision_authoring,
    list_recipe_drafts,
    publish_recipe_draft,
    update_recipe_draft,
)
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
    assess_study_validation_pair,
    compare_study_runs,
    create_quality_policy,
    declare_study_holdout_use,
    diff_quality_policies,
    evaluate_study_run,
    get_quality_policy,
    get_study_champion,
    get_study_prediction_access,
    get_study_validation_resolutions,
    list_quality_policies,
    list_study_decisions,
    list_study_evaluations,
    recommend_study_run,
    retire_quality_policy,
)
from .tools.recipes import (
    create_study_recipe,
    diff_recipe_revisions,
    get_recipe_revision,
    list_study_recipes,
    refreeze_recipe_revision,
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
    create_study,
    get_launch_eligibility,
    get_study,
    get_study_overview,
    get_study_run,
    launch_study_run,
    list_studies,
    list_study_runs,
    update_study,
)

mcp = MCPServer(
    name="Simba MMM",
    version=runtime._own_version(),
    instructions=(
        "Simba is a Bayesian Marketing Mix Modeling (MMM) platform. "
        "Use these tools to upload marketing data, build MMM models, "
        "check fitting progress, retrieve results (channel ROI, contributions, "
        "model diagnostics), and run budget optimizations. "
        "Start with get_backend_capabilities and get_data_schema. For studies: inspect "
        "the project and budget, validate/freeze a recipe, declare a quality policy, "
        "then launch using an explicit submission_key. Reuse that key and identical "
        "inputs after an uncertain launch. Poll shared run progress; cancellation "
        "requested is not cancellation completed. Reload after revision conflicts. "
        "Evaluate existing evidence and recommend with limitations; analyst acceptance "
        "is in the frontend. Missing evidence never passes and fitted-window metrics "
        "are not holdout validation. Use selected result sections and bounds. "
        "Writes are not automatically retried; reconcile before repeating them."
    ),
    lifespan=app_lifespan,
)

TOOLS = (
    create_recipe_draft,
    get_recipe_draft,
    get_recipe_draft_template,
    publish_recipe_draft,
    get_recipe_revision_authoring,
    list_recipe_drafts,
    update_recipe_draft,
    get_backend_capabilities,
    get_data_schema,
    upload_data,
    list_pipeline_versions,
    list_pipelines,
    list_uploads,
    get_upload,
    list_models,
    create_model,
    create_var_model,
    link_var_model,
    unlink_var_model,
    set_contribution_groups,
    get_contribution_groups,
    rename_model,
    save_model,
    unsave_model,
    list_projects,
    create_project,
    rename_project,
    get_model,
    delete_model,
    get_model_status,
    get_model_results,
    run_optimizer,
    get_optimizer_results,
    get_scenario_template,
    run_scenario,
    get_scenario_results,
    update_run,
    set_run_pinned,
    list_runs,
    list_studies,
    create_study,
    get_study,
    get_launch_eligibility,
    get_study_overview,
    update_study,
    list_study_recipes,
    create_study_recipe,
    revise_study_recipe,
    get_recipe_revision,
    diff_recipe_revisions,
    refreeze_recipe_revision,
    validate_study_recipe,
    launch_study_run,
    list_study_runs,
    get_study_run,
    cancel_study_run,
    list_quality_policies,
    diff_quality_policies,
    get_quality_policy,
    create_quality_policy,
    retire_quality_policy,
    evaluate_study_run,
    list_study_evaluations,
    list_study_decisions,
    get_study_champion,
    get_study_prediction_access,
    get_study_validation_resolutions,
    declare_study_holdout_use,
    assess_study_validation_pair,
    recommend_study_run,
    adopt_model_into_study,
    compare_study_runs,
)


def _wire_errors(tool):
    """A refused backend call is a tool execution error on the wire (jellyfish #824).

    The structured payload (`error`, `_status_code`, `_error_code`, `_next_action`, extras)
    stays exactly as before for clients that read it; `isError` is now also true, so a client
    that only checks the flag no longer mistakes a refusal for success. Successful results
    pass through untouched.
    """

    @functools.wraps(tool)
    async def wrapped(*args, **kwargs):
        result = await tool(*args, **kwargs)
        status = result.get("_status_code") if isinstance(result, dict) else None
        if isinstance(status, int) and status >= 400:
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(result))],
                structured_content=result,
                is_error=True,
            )
        return result

    return wrapped


for tool in TOOLS:
    mcp.add_tool(
        _wire_errors(tool),
        title=tool.__name__.replace("_", " ").title(),
        annotations=annotations_for(tool.__name__),
    )


def _create_app():
    return runtime.create_app(mcp)


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
    "_norm_channel",
    "adopt_model_into_study",
    "app_lifespan",
    "assess_study_validation_pair",
    "cancel_study_run",
    "compare_study_runs",
    "create_model",
    "create_project",
    "create_quality_policy",
    "create_study",
    "create_study_recipe",
    "create_var_model",
    "declare_study_holdout_use",
    "delete_model",
    "diff_quality_policies",
    "evaluate_study_run",
    "get_contribution_groups",
    "get_data_schema",
    "get_launch_eligibility",
    "get_model",
    "get_model_results",
    "get_model_status",
    "get_optimizer_results",
    "get_quality_policy",
    "get_recipe_revision",
    "get_scenario_results",
    "get_scenario_template",
    "get_study",
    "get_study_champion",
    "get_study_overview",
    "get_study_prediction_access",
    "get_study_run",
    "get_study_validation_resolutions",
    "get_upload",
    "launch_study_run",
    "link_var_model",
    "list_models",
    "list_pipeline_versions",
    "list_pipelines",
    "list_projects",
    "list_quality_policies",
    "list_runs",
    "list_studies",
    "list_study_decisions",
    "list_study_evaluations",
    "list_study_recipes",
    "list_study_runs",
    "list_uploads",
    "recommend_study_run",
    "refreeze_recipe_revision",
    "rename_model",
    "rename_project",
    "retire_quality_policy",
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
