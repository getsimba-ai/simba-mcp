"""Studies tools backed by the Simba API."""

from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from ..auth import _client
from ..runtime import AppContext
from .pagination import page


async def list_studies(
    project_id: int,
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
    """List project-owned studies, questions, budgets and access rights."""
    payload = await _client(ctx).workflow_request("GET", f"/projects/{project_id}/studies")

    return page(payload, "studies", limit, offset)


async def create_study(
    project_id: int,
    name: str,
    question: str,
    max_attempts: Annotated[
        int,
        Field(
            description="Maximum new fitting attempts permitted by the study; creating a study does not launch them."
        ),
    ] = 5,
    max_concurrent: Annotated[
        int, Field(description="Maximum concurrent fitting attempts within this study.")
    ] = 1,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Create a study owned by an existing project. Does not launch models."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/projects/{project_id}/studies",
        {
            "name": name,
            "question": question,
            "max_attempts": max_attempts,
            "max_concurrent": max_concurrent,
        },
    )


async def get_study(
    study_id: Annotated[
        str,
        Field(
            description="Identifier of the existing study; project permissions are checked by Simba."
        ),
    ],
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Read a study and its optimistic concurrency version."""
    return await _client(ctx).workflow_request("GET", f"/studies/{study_id}")


async def update_study(
    study_id: Annotated[
        str,
        Field(
            description="Identifier of the existing study; project permissions are checked by Simba."
        ),
    ],
    version: Annotated[
        int,
        Field(
            description="Current optimistic concurrency version. Read the object again after a conflict."
        ),
    ],
    name: str,
    question: str,
    max_attempts: Annotated[
        int,
        Field(
            description="Maximum new fitting attempts permitted by the study; creating a study does not launch them."
        ),
    ],
    max_concurrent: Annotated[
        int, Field(description="Maximum concurrent fitting attempts within this study.")
    ],
    state: Annotated[
        str,
        Field(
            description="Study lifecycle value: active, paused or archived. Active permits launches; it does not mean a fit is running."
        ),
    ] = "active",
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Update owner-controlled study settings. State is active, paused or archived. Stale versions fail."""
    return await _client(ctx).workflow_request(
        "PATCH",
        f"/studies/{study_id}",
        {
            "version": version,
            "name": name,
            "question": question,
            "max_attempts": max_attempts,
            "max_concurrent": max_concurrent,
            "state": state,
        },
    )


async def launch_study_run(
    study_id: Annotated[
        str,
        Field(
            description="Identifier of the existing study; project permissions are checked by Simba."
        ),
    ],
    revision_id: Annotated[
        str,
        Field(
            description="Exact immutable recipe revision identifier, not the latest recipe name."
        ),
    ],
    policy_id: Annotated[
        str, Field(description="Exact quality policy identifier to pin to the run or evaluation.")
    ],
    submission_key: Annotated[
        str,
        Field(
            description="Stable caller-generated key for this launch. Reuse it with identical revision and policy after an uncertain response."
        ),
    ],
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Launch a frozen revision within study budget. Reuse the same submission_key after an ambiguous response; never invent another key for a retry."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/runs",
        {"revision_id": revision_id, "policy_id": policy_id, "submission_key": submission_key},
    )


async def list_study_runs(
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
    """List preserved attempts including pending and failed runs."""
    payload = await _client(ctx).workflow_request("GET", f"/studies/{study_id}/runs")

    return page(payload, "runs", limit, offset)


async def get_study_run(
    run_id: str,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Read durable run status and the linked model."""
    return await _client(ctx).workflow_request("GET", f"/study-runs/{run_id}")


async def cancel_study_run(
    run_id: str,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Request cancellation. Requested and confirmed stopped are distinct states."""
    return await _client(ctx).workflow_request("POST", f"/study-runs/{run_id}/cancel", {})


async def adopt_model_into_study(
    study_id: Annotated[
        str,
        Field(
            description="Identifier of the existing study; project permissions are checked by Simba."
        ),
    ],
    model_hash: str,
    reason: Annotated[
        str, Field(description="Human-readable rationale retained in the study history.")
    ],
    confirm: bool = False,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Preview an owned completed model and provenance gaps. Set confirm only to attach it to study history; adoption does not refit."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/adoptions",
        {"model_hash": model_hash, "reason": reason, "confirm": confirm},
    )


async def compare_study_runs(
    study_id: Annotated[
        str,
        Field(
            description="Identifier of the existing study; project permissions are checked by Simba."
        ),
    ],
    run_ids: list[str],
    policy_id: Annotated[
        str, Field(description="Exact quality policy identifier to pin to the run or evaluation.")
    ],
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Compare 2-20 candidates against one quality policy. Different datasets are flagged, not ranked. Does not fit or promote models."""
    return await _client(ctx).workflow_request(
        "POST", f"/studies/{study_id}/comparisons", {"run_ids": run_ids, "policy_id": policy_id}
    )


def register(mcp: MCPServer) -> None:
    mcp.tool(
        title="List studies",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(list_studies)
    mcp.tool(
        title="Create study",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )(create_study)
    mcp.tool(
        title="Get study",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(get_study)
    mcp.tool(
        title="Update study",
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=True
        ),
    )(update_study)
    mcp.tool(
        title="Launch study run",
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(launch_study_run)
    mcp.tool(
        title="List study runs",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(list_study_runs)
    mcp.tool(
        title="Get study run",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(get_study_run)
    mcp.tool(
        title="Cancel study run",
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=True
        ),
    )(cancel_study_run)
    mcp.tool(
        title="Adopt model into study",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )(adopt_model_into_study)
    mcp.tool(
        title="Compare study runs",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(compare_study_runs)
