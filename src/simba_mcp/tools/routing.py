"""Optional workflow recommendation, never an executor or permission decision."""

from typing import Any

from mcp.server.mcpserver import Context
from pydantic import ValidationError

from ..auth import _client
from ..errors import api_error
from ..guidance.routing import WORKFLOWS, fallback, recommendation, validate_request
from ..profiles import PROFILES
from ..runtime import AppContext
from ..user_profiles import CURRENT_PROFILE


async def recommend_workflow(request: str, ctx: Context[AppContext, Any]) -> dict[str, Any]:
    """Recommend guidance and visible tools for an ambiguous Simba workflow.

    Optional: skip when the workflow is already clear or relevant guidance is loaded.
    Sends up to 4,000 UTF-8 bytes of user intent to the authenticated Simba backend,
    which may use OpenAI Decisions when enabled. Do not include secrets or raw data.
    Returns advisory guidance references and a bounded tool shortlist, not executable
    arguments or permission. Continue using existing tools and backend policies.
    On fallback continue normal selection; do not automatically retry this paid call.
    This does not shrink a catalogue already loaded by your assistant.
    """
    try:
        validate_request(request)
    except ValueError as exc:
        return api_error(400, {"code": "invalid_routing_request", "error": str(exc)})
    result = await _client(ctx).workflow_request(
        "POST", "/mcp/workflow-recommendations", {"schema_version": 1, "request": request}
    )
    if isinstance(result, dict) and result.get("_status_code", 200) != 200:
        if result.get("_status_code") in (401, 403, 400, 413):
            return result
        result = fallback("provider_error")
    app = ctx.request_context.lifespan_context
    visible = set(app.tool_names or {name for _, tools in WORKFLOWS.values() for name in tools})
    account_profile = CURRENT_PROFILE.get()
    if account_profile in PROFILES:
        visible.intersection_update(PROFILES[account_profile])
    try:
        return recommendation(result, visible)
    except (ValidationError, TypeError):
        return recommendation(fallback("invalid_answer"), visible)
