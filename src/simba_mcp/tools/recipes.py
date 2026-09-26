"""Recipes tools backed by the shared Simba API."""

from typing import Any, Literal

from mcp.server.mcpserver import Context

from ..auth import _client, _page
from ..runtime import AppContext
from ..schemas import APIResult, RecipeSpecification


async def list_study_recipes(
    study_id: str,
    limit: int | None = None,
    cursor: str | None = None,
    expand: list[Literal["effective", "inspection", "specification"]] | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """List recipes with their revisions as summaries (id, number, content_hash, reason, created_at). Heavy fields travel only by name in expand: effective (exact frozen priors, settings, data hashes and runtime), inspection (which settings were authored vs defaulted, inert prior fields with their gate, engine state current/stale that predicts whether launch will be refused; treat inert values as stored-but-unused, not as recipe errors), specification (the authored request). Prefer get_recipe_revision for one revision in full. Raw datasets are never included. Paging is opt-in: pass limit (1-200) to receive a page and next_cursor; send that cursor back unchanged for the next page; null next_cursor means the end. Without limit every row is returned. Rows you cannot see are simply absent; no totals are promised."""
    return await _client(ctx).workflow_request(
        "GET", f"/studies/{study_id}/recipes", params=_page(limit, cursor, expand)
    )


async def create_study_recipe(
    study_id: str,
    name: str,
    reason: str,
    specification: RecipeSpecification,
    ctx: Context[AppContext, Any] = None,
    expected_content_hash: str | None = None,
    source_revision_id: str | None = None,
) -> APIResult:
    """Freeze a recipe without fitting. Supply source_revision_id when deriving from a published same-study recipe to retain influence ancestry. Optional expected_content_hash binds the validated effective inputs; a mismatch returns 409 and requires a fresh preview. Specification kind api_mmm has request containing create_model API fields; model_snapshot has model_hash and is review-only."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/recipes",
        {
            "name": name,
            "reason": reason,
            "specification": specification,
            **(
                {"source_revision_id": source_revision_id} if source_revision_id is not None else {}
            ),
            "expected_version": 0,
            **(
                {"expected_content_hash": expected_content_hash}
                if expected_content_hash is not None
                else {}
            ),
        },
    )


async def revise_study_recipe(
    recipe_id: str,
    expected_version: int,
    name: str,
    reason: str,
    specification: RecipeSpecification,
    ctx: Context[AppContext, Any] = None,
    expected_content_hash: str | None = None,
    source_revision_id: str | None = None,
) -> APIResult:
    """Create an immutable revision. Earlier versions inherit influence automatically; optional source_revision_id additionally links a same-study source recipe. Optional expected_content_hash guards effective inputs (409 requires a fresh preview). Supply the current recipe version; stale edits are rejected (412). Reload list_study_recipes, reconcile changes, then submit the current version; never overwrite blindly."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/recipes/{recipe_id}/revisions",
        {
            "name": name,
            "reason": reason,
            "specification": specification,
            **(
                {"source_revision_id": source_revision_id} if source_revision_id is not None else {}
            ),
            "expected_version": expected_version,
            **(
                {"expected_content_hash": expected_content_hash}
                if expected_content_hash is not None
                else {}
            ),
        },
    )


async def refreeze_recipe_revision(
    recipe_id: str,
    number: int,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Recover from engine_changed without bypassing the safeguard: creates a new revision of the same recipe with the same specification, frozen on the current engine, with an auto-filled reason naming what changed. The old revision and its provenance are untouched. Returns the new revision; launch that one. 409 conflict when the revision is already frozen on the current engine; 409 snapshot_not_executable for review-only snapshots."""
    return await _client(ctx).workflow_request(
        "POST", f"/recipes/{recipe_id}/revisions/{number}/refreeze"
    )


async def get_recipe_revision(
    recipe_id: str,
    number: int,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Read one immutable revision with its inspection block. settings.<key>.value is what a fit of this revision would use, including fitter defaults for absent keys (status authored or default); effective.form_data is what was authored. priors[].fields lists conditional prior fields that were stored but never read for that row's adstock type or the saturation family (status inert, with the gate that would make them live); treat them as stored-but-unused and do not "fix" them by editing unless the gating setting changes too. engine.state current or stale predicts whether launch will be refused. Absent configuration classifies nothing."""
    return await _client(ctx).workflow_request("GET", f"/recipes/{recipe_id}/revisions/{number}")


async def validate_study_recipe(
    specification: RecipeSpecification,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Resolve and validate a recipe without creating a run. Returns effective settings, provenance limits and the same inspection block a saved revision would carry (authored/default settings, inert prior fields with their gate, engine state), so an agent can check for inert fields before freezing."""
    return await _client(ctx).workflow_request(
        "POST", "/recipe-validation", {"specification": specification}
    )


async def diff_recipe_revisions(
    recipe_id: str,
    base: int,
    other: int,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """What changed between two revisions of one recipe, with the viewer's labels (jellyfish #881): settings[] (key, section, label, from, to), priors[] (row, parameter, column, label, from, to), data (dataset origin and input-hash change, or null) and counts {settings, priors, data, total}, plus base and other {number, id}. Blank equals absent; prior rows are matched by variable and role. Read this after publishing revision N+1 to state exactly what an edit changed. 404 when the recipe or either revision is missing. Read-only."""
    return await _client(ctx).workflow_request(
        "GET", f"/recipes/{recipe_id}/revisions/{base}/diff/{other}"
    )
