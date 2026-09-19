from .pagination import page

"""Recipes tools backed by the Simba API."""

from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from ..auth import _client
from ..runtime import AppContext


async def list_study_recipes(
    study_id: Annotated[
        str,
        Field(
            description="Identifier of the existing study; project permissions are checked by Simba."
        ),
    ],
    ctx: Context[AppContext, Any] = None,
    *,
    limit: Annotated[
        int | None,
        Field(
            description="Maximum records to return. Existing endpoint defaults apply; workflow lists allow 1-200, or null to preserve the full legacy response."
        ),
    ] = None,
    offset: Annotated[
        int,
        Field(
            description="Zero-based record offset. Concurrent changes can shift page boundaries."
        ),
    ] = 0,
) -> dict[str, Any]:
    """Read all recipe revisions including exact effective priors, settings and data hashes. Raw datasets are omitted."""
    payload = await _client(ctx).workflow_request("GET", f"/studies/{study_id}/recipes")

    return page(payload, "recipes", limit, offset)


async def create_study_recipe(
    study_id: Annotated[
        str,
        Field(
            description="Identifier of the existing study; project permissions are checked by Simba."
        ),
    ],
    name: str,
    reason: Annotated[
        str, Field(description="Human-readable rationale retained in the study history.")
    ],
    specification: Annotated[
        dict,
        Field(
            description="Backend recipe specification. api_mmm contains request settings; model_snapshot records an existing model. Validate with validate_study_recipe before saving."
        ),
    ],
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Freeze a recipe without fitting. Specification kind api_mmm has request containing create_model API fields; model_snapshot has model_hash and is review-only."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/recipes",
        {"name": name, "reason": reason, "specification": specification, "expected_version": 0},
    )


async def revise_study_recipe(
    recipe_id: Annotated[
        str,
        Field(description="Identifier of the recipe whose immutable history is being accessed."),
    ],
    expected_version: int,
    name: str,
    reason: Annotated[
        str, Field(description="Human-readable rationale retained in the study history.")
    ],
    specification: Annotated[
        dict,
        Field(
            description="Backend recipe specification. api_mmm contains request settings; model_snapshot records an existing model. Validate with validate_study_recipe before saving."
        ),
    ],
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
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
    recipe_id: Annotated[
        str,
        Field(description="Identifier of the recipe whose immutable history is being accessed."),
    ],
    number: int,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Read one exact immutable recipe revision."""
    return await _client(ctx).workflow_request("GET", f"/recipes/{recipe_id}/revisions/{number}")


async def validate_study_recipe(
    specification: Annotated[
        dict,
        Field(
            description="Backend recipe specification. api_mmm contains request settings; model_snapshot records an existing model. Validate with validate_study_recipe before saving."
        ),
    ],
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Resolve and validate a recipe without creating a run. Returns effective settings and provenance limits."""
    return await _client(ctx).workflow_request(
        "POST", "/recipe-validation", {"specification": specification}
    )


def register(mcp: MCPServer) -> None:
    mcp.tool(
        title="List study recipes",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(list_study_recipes)
    mcp.tool(
        title="Create study recipe",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )(create_study_recipe)
    mcp.tool(
        title="Revise study recipe",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )(revise_study_recipe)
    mcp.tool(
        title="Get recipe revision",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(get_recipe_revision)
    mcp.tool(
        title="Validate study recipe",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(validate_study_recipe)
