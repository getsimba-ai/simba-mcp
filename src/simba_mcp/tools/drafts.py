"""Versioned authoring drafts and explicit immutable publication; never launches a model."""

from typing import Any, Literal

from mcp.server.mcpserver import Context

from ..auth import _client, _page
from ..runtime import AppContext
from ..schemas import APIResult, DraftSnapshot, DraftTarget, PublishTarget


async def get_recipe_draft_template(
    family: Literal["mmm", "var"] = "mmm",
    uploaded_file_id: int | None = None,
    pipeline_version_id: int | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Get complete shared wizard defaults, hash and envelope schema. Optionally choose an owned uploaded_file_id (from list_uploads) or pipeline_version_id (from list_pipelines / list_pipeline_versions), never both, into frozen source bytes with verified lineage and an editable data preview. Copy snapshot into create_recipe_draft and preserve unedited fields. Defaults are not a validated model. Does not create, publish or run anything."""
    path = f"/recipe-draft-template?family={family}"
    if uploaded_file_id is not None:
        path += f"&uploaded_file_id={uploaded_file_id}"
    if pipeline_version_id is not None:
        path += f"&pipeline_version_id={pipeline_version_id}"
    return await _client(ctx).workflow_request("GET", path)


async def list_recipe_drafts(
    study_id: str,
    limit: int | None = None,
    cursor: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """List study draft metadata without loading datasets, newest update first. Check backend draft capability first. Paging is opt-in: pass limit (1-200) to receive a page and next_cursor; send that cursor back unchanged for the next page; null next_cursor means the end. Without limit every row is returned. Rows you cannot see are simply absent; no totals are promised."""
    return await _client(ctx).workflow_request(
        "GET", f"/studies/{study_id}/recipe-drafts", params=_page(limit, cursor)
    )


async def get_recipe_draft(draft_id: str, ctx: Context[AppContext, Any] = None) -> APIResult:
    """Read the complete authoring snapshot and concurrency version. Preserve all fields when editing. Draft state is incomplete, unvalidated authoring data, not an executable recipe."""
    return await _client(ctx).workflow_request("GET", f"/recipe-drafts/{draft_id}")


async def create_recipe_draft(
    study_id: str,
    draft_id: str,
    name: str,
    snapshot: DraftSnapshot,
    ctx: Context[AppContext, Any] = None,
    source_revision_id: str | None = None,
    target: DraftTarget | None = None,
) -> APIResult:
    """Save an encrypted authoring draft without publishing, fitting or consuming an attempt. Supply a UUID draft_id and reuse it with identical content after an uncertain response. Start from get_recipe_draft_template for a new draft, or from get_recipe_revision_authoring when working from a published revision. To edit a recipe in place, pass target={recipe_id, base_revision_id}: the draft becomes an edit session of that recipe and publish_recipe_draft with a matching target writes the recipe's next revision; the target is immutable after creation (409 on a replay that names another; 404 for a recipe outside the study). To branch a published recipe into a new one instead, omit target and supply its source_revision_id from this study; the immutable link carries inherited influence through publication. Backend validates version and size."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/recipe-drafts",
        {
            "id": draft_id,
            "name": name,
            "snapshot": snapshot,
            **(
                {"source_revision_id": source_revision_id} if source_revision_id is not None else {}
            ),
            **({"target": target} if target is not None else {}),
        },
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


async def publish_recipe_draft(
    draft_id: str,
    expected_version: int,
    publication_id: str,
    reason: str,
    ctx: Context[AppContext, Any] = None,
    target: PublishTarget | None = None,
) -> APIResult:
    """Publish a saved MMM or VAR draft as immutable recipe revisions. Supply a new UUID publication_id and reuse it with identical arguments after an uncertain response; a replay returns the same revisions. Without target: new recipes, one per prepared brand, atomic. With target={recipe_id, expected_version}: revision N+1 of that recipe under its row lock, the draft's base revision recorded as the source. 412 stale_version when the recipe moved since expected_version: the draft and every edit are kept, so re-read the recipe and publish again on top, or drop target to branch into a new recipe. 409 target_requires_single_recipe for a multi-brand draft; 409 when the draft's own target names a different recipe; 404 for a recipe outside the study. Backend compiles the saved snapshot with shared wizard rules; never send separately prepared settings. Does not fit, consume an attempt or designate a champion. Automatic MMM priors are resolved at publication and frozen; replay does not rebuild them. VAR requires family-specific evidence assessment; MMM policies cannot establish VAR acceptance. Enabled invalid MMM calibration fails publication; VAR calibration is unsupported. Preserve disabled authoring observations."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/recipe-drafts/{draft_id}/publish",
        {
            "expected_version": expected_version,
            "publication_id": publication_id,
            "reason": reason,
            **({"target": target} if target is not None else {}),
        },
    )


async def get_recipe_revision_authoring(
    recipe_id: str,
    number: int,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Read the authoring snapshot behind a published revision. authoring_draft, wizard (Save a recipe) and base_model (imported fitted model) revisions carry one; api_mmm, model_snapshot and legacy rows return an explicit unavailable error (404). Returns snapshot, name, revision_id, draft_content_hash, kind, source_available and source_unavailable_reason. Dataset bytes are filled from the recorded origin only when it still hashes to what was fitted; otherwise snapshot.source is null, source_available is false and the reason says to choose the dataset again before the draft can publish. Use the snapshot with create_recipe_draft: target for an in-place edit, source_revision_id for a branch. The published revision stays unchanged. Does not create or fit anything."""
    return await _client(ctx).workflow_request(
        "GET", f"/recipes/{recipe_id}/revisions/{number}/authoring"
    )
