"""Versioned authoring drafts; saving never launches or publishes a model."""

from typing import Any, Literal

from mcp.server.mcpserver import Context

from ..auth import _client
from ..runtime import AppContext
from ..schemas import APIResult, DraftSnapshot


async def get_recipe_draft_template(
    family: Literal["mmm", "var"] = "mmm",
    uploaded_file_id: int | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Get complete shared wizard defaults, hash and envelope schema. Optionally copy an owned uploaded_file_id into frozen source bytes with verified lineage and an editable data preview. Copy snapshot into create_recipe_draft and preserve unedited fields. Defaults are not a validated model. Does not create, publish or run anything."""
    path = f"/recipe-draft-template?family={family}"
    if uploaded_file_id is not None:
        path += f"&uploaded_file_id={uploaded_file_id}"
    return await _client(ctx).workflow_request("GET", path)


async def list_recipe_drafts(study_id: str, ctx: Context[AppContext, Any] = None) -> APIResult:
    """List study draft metadata without loading datasets. Check backend draft capability first."""
    return await _client(ctx).workflow_request("GET", f"/studies/{study_id}/recipe-drafts")


async def get_recipe_draft(draft_id: str, ctx: Context[AppContext, Any] = None) -> APIResult:
    """Read the complete authoring snapshot and concurrency version. Preserve all fields when editing. Draft state is incomplete, unvalidated authoring data, not an executable recipe."""
    return await _client(ctx).workflow_request("GET", f"/recipe-drafts/{draft_id}")


async def create_recipe_draft(
    study_id: str,
    draft_id: str,
    name: str,
    snapshot: DraftSnapshot,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Save an encrypted authoring draft without publishing, fitting or consuming an attempt. Supply a UUID draft_id and reuse it with identical content after an uncertain response. Start from get_recipe_draft_template for a new draft, or preserve the complete snapshot from get_recipe_draft when editing. Backend validates version and size."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/recipe-drafts",
        {"id": draft_id, "name": name, "snapshot": snapshot},
    )


async def update_recipe_draft(
    draft_id: str,
    expected_version: int,
    name: str,
    snapshot: DraftSnapshot,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Replace authoring state using the version from get_recipe_draft. Retain every unedited field, including original priors and source bytes. Stale changes fail; reload and reconcile explicitly. Identical retries return the current draft. Does not publish or launch."""
    return await _client(ctx).workflow_request(
        "PATCH",
        f"/recipe-drafts/{draft_id}",
        {"expected_version": expected_version, "name": name, "snapshot": snapshot},
    )
