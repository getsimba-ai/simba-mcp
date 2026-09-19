"""Versioned authoring drafts; saving never launches or publishes a model."""

from typing import Any

from mcp.server.mcpserver import Context

from ..auth import _client
from ..runtime import AppContext
from ..schemas import APIResult, DraftSnapshot


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
    """Save an encrypted authoring draft without publishing, fitting or consuming an attempt. Supply a UUID draft_id and reuse it with identical content after an uncertain response. Backend validates version and size. UI-reopenable snapshots must retain the complete editor schema returned by get_recipe_draft."""
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
