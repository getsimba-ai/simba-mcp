"""Recipes tools backed by the shared Simba API."""

from typing import Any

from mcp.server.mcpserver import Context

from ..auth import _client
from ..runtime import AppContext


async def list_study_recipes(
    study_id: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Read all recipe revisions including exact effective priors, settings and data hashes. Raw datasets are omitted."""
    return await _client(ctx).workflow_request("GET", f"/studies/{study_id}/recipes")


async def create_study_recipe(
    study_id: str,
    name: str,
    reason: str,
    specification: dict,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Freeze a recipe without fitting. Specification kind api_mmm has request containing create_model API fields; model_snapshot has model_hash and is review-only."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/recipes",
        {"name": name, "reason": reason, "specification": specification, "expected_version": 0},
    )


async def revise_study_recipe(
    recipe_id: str,
    expected_version: int,
    name: str,
    reason: str,
    specification: dict,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Create an immutable revision. Supply the current recipe version; stale edits are rejected."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/recipes/{recipe_id}/revisions",
        {
            "name": name,
            "reason": reason,
            "specification": specification,
            "expected_version": expected_version,
        },
    )


async def get_recipe_revision(
    recipe_id: str,
    number: int,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Read one exact immutable recipe revision."""
    return await _client(ctx).workflow_request("GET", f"/recipes/{recipe_id}/revisions/{number}")


async def validate_study_recipe(
    specification: dict,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Resolve and validate a recipe without creating a run. Returns effective settings and provenance limits."""
    return await _client(ctx).workflow_request(
        "POST", "/recipe-validation", {"specification": specification}
    )
