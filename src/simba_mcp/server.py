"""Simba MCP composition and registration. Backend services own durable state."""

import functools
import json
import os

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp.types import CallToolResult, TextContent
from pydantic import ValidationError

from . import runtime, telemetry
from .api_client import CALLER_API_KEY
from .auth import _bearer_token, _client, _local_files_allowed
from .catalogue import description_for
from .errors import api_error
from .metadata import annotations_for
from .profiles import select_tools
from .runtime import (
    MAX_REQUEST_BODY_BYTES,
    MAX_UPLOAD_BYTES,
    AppContext,
    app_lifespan,
    set_http_mode,
)
from .tools.data import (
    get_backend_capabilities,
    get_data_report,
    get_data_schema,
    get_pipeline_run,
    get_upload,
    list_pipeline_versions,
    list_pipelines,
    list_uploads,
    run_pipeline,
    set_pipeline_schedule,
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
from .tools.guidance import get_workflow_guidance
from .tools.incrementality import (
    create_incrementality_test,
    get_incrementality_test,
    import_incrementality_tests,
    list_incrementality_tests,
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


def _argument_refusal(tool: str, exc: ValidationError) -> CallToolResult:
    """The envelope for arguments that fail a tool's input schema (simba-mcp#26).

    Field paths and pydantic's reason only: the rejected values are the caller's data (possibly
    dataset contents) and never go back on the wire."""
    fields = [
        {
            "field": ".".join(str(part) for part in err["loc"]),
            "problem": err["msg"],
            "type": err["type"],
        }
        for err in exc.errors()
    ]
    names = ", ".join(sorted({f["field"] for f in fields})) or "arguments"
    payload = api_error(
        422,
        {
            "error": f"Arguments do not match the input schema of {tool}: {names}.",
            "code": "invalid_arguments",
            "fields": fields,
        },
    )
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload))],
        structured_content=payload,
        is_error=True,
    )


class SimbaMCPServer(MCPServer):
    """MCPServer whose argument-validation refusals carry the same envelope as every other
    refusal (`code`, `_status_code`, `_error_code`, `_next_action`).

    The SDK validates arguments before a tool body runs and reports a failure as plain text;
    `_wire_errors` wraps tool bodies and so never sees it (simba-mcp#26)."""

    _simba_http_mode = False

    def streamable_http_app(self, **kwargs):
        self._simba_http_mode = True
        return super().streamable_http_app(**kwargs)

    def sse_app(self, **kwargs):
        self._simba_http_mode = True
        return super().sse_app(**kwargs)

    def run(self, transport="stdio", **kwargs):
        self._simba_http_mode = transport != "stdio"
        return super().run(transport=transport, **kwargs)

    async def call_tool(self, name, arguments, context=None):
        token = CALLER_API_KEY.set(CALLER_API_KEY.get())
        try:
            return await self._observed_call(name, arguments, context)
        finally:
            CALLER_API_KEY.reset(token)

    async def _observed_call(self, name, arguments, context):
        sink = telemetry.get_sink()
        if sink is None:
            return await self._call_tool(name, arguments, context)
        with telemetry.observe(name if name in _TOOL_NAMES else "other", sink) as observation:
            result = await self._call_tool(name, arguments, context)
            observation.result(result)
            return result

    async def _call_tool(self, name, arguments, context=None):
        try:
            return await super().call_tool(name, arguments, context)
        except ToolError as exc:
            if not isinstance(exc, UnexpectedToolError) and isinstance(
                exc.__cause__, ValidationError
            ):
                return _argument_refusal(name, exc.__cause__)
            raise


_SERVER_OPTIONS = {
    "name": "Simba MMM",
    "version": runtime._own_version(),
    "instructions": (
        "Simba is a Bayesian Marketing Mix Modeling (MMM) platform. "
        "Use these tools to upload marketing data, build MMM models, "
        "check fitting progress, retrieve results (channel ROI, contributions, "
        "model diagnostics), and run budget optimizations. "
        "For new data use get_data_schema; discover capabilities when the planned operation "
        "requires them. Existing-result questions can start with selected results directly. "
        "If native Skills are unavailable, use get_workflow_guidance for relevant guidance. "
        "For studies: inspect "
        "the project and budget, validate/freeze a recipe, declare a quality policy, "
        "then launch using an explicit submission_key. Reuse that key and identical "
        "inputs after an uncertain launch. Poll shared run progress; cancellation "
        "requested is not cancellation completed. Reload after revision conflicts. "
        "Evaluate existing evidence and recommend with limitations; analyst acceptance "
        "is in the frontend. Missing evidence never passes and fitted-window metrics "
        "are not holdout validation. Use selected result sections and bounds. "
        "Writes are not automatically retried; reconcile before repeating them."
    ),
    "lifespan": app_lifespan,
}

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
    get_data_report,
    upload_data,
    list_pipeline_versions,
    list_pipelines,
    run_pipeline,
    get_pipeline_run,
    set_pipeline_schedule,
    list_incrementality_tests,
    get_incrementality_test,
    create_incrementality_test,
    import_incrementality_tests,
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
    get_workflow_guidance,
)


_TOOL_NAMES = frozenset(tool.__name__ for tool in TOOLS)


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


def create_server(description_mode: str = "legacy", *, profile: str = "full") -> SimbaMCPServer:
    """Build an immutable catalogue using the same contracts and execution wrappers."""
    if description_mode not in ("legacy", "compact"):
        raise ValueError("SIMBA_TOOL_DESCRIPTIONS must be legacy or compact")
    selected = select_tools(TOOLS, profile)
    options = dict(_SERVER_OPTIONS)
    if profile not in ("full", "data_scientist"):
        options["instructions"] = (
            f"This is the optional {profile} tool view. Use only listed tools. "
            "For a task requiring an omitted tool, explain that the user can reconnect "
            "to a full-profile server (SIMBA_TOOL_PROFILE=full or --profile full). "
            "Do not invent missing tools or replay an uncertain write after switching. "
            "Profiles do not grant backend permissions. Use get_workflow_guidance for "
            "relevant guidance and selected result sections for existing evidence. "
            "Missing evidence never passes. Fitted-window metrics are not holdout validation. "
            "Recommendations are not analyst acceptance. Poll the exact saved run ID; "
            "a successful HTTP response does not mean a run completed successfully."
        )
    instance = SimbaMCPServer(**options)
    for tool in selected:
        instance.add_tool(
            _wire_errors(tool),
            title=tool.__name__.replace("_", " ").title(),
            description=description_for(tool, description_mode),
            annotations=annotations_for(tool.__name__),
        )
    return instance


TOOL_DESCRIPTION_MODE = os.environ.get("SIMBA_TOOL_DESCRIPTIONS", "legacy")
TOOL_PROFILE = os.environ.get("SIMBA_TOOL_PROFILE", "full")
mcp = create_server(TOOL_DESCRIPTION_MODE, profile=TOOL_PROFILE)


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
    "create_incrementality_test",
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
    "get_data_report",
    "get_data_schema",
    "get_incrementality_test",
    "get_launch_eligibility",
    "get_model",
    "get_model_results",
    "get_model_status",
    "get_optimizer_results",
    "get_pipeline_run",
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
    "import_incrementality_tests",
    "launch_study_run",
    "link_var_model",
    "list_incrementality_tests",
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
    "run_pipeline",
    "run_scenario",
    "save_model",
    "set_contribution_groups",
    "set_http_mode",
    "set_pipeline_schedule",
    "set_run_pinned",
    "unlink_var_model",
    "unsave_model",
    "update_run",
    "update_study",
    "upload_data",
    "validate_study_recipe",
]
