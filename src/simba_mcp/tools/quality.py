"""Quality tools backed by the Simba API."""

from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from ..auth import _client
from ..runtime import AppContext
from .pagination import page


async def list_quality_policies(
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
    """Read immutable quality policies for the study."""
    payload = await _client(ctx).workflow_request("GET", f"/studies/{study_id}/quality-policies")

    return page(payload, "policies", limit, offset)


async def create_quality_policy(
    study_id: Annotated[
        str,
        Field(
            description="Identifier of the existing study; project permissions are checked by Simba."
        ),
    ],
    name: str,
    rationale: str,
    checks: Annotated[
        list[dict],
        Field(
            description="Quality criteria with metric, maximum and optional required flag. Metrics: r_hat_max (dimensionless), mae/rmse (saved actual_vs_model units), wape (fraction, so 0.10 means 10%). Missing evidence is not a pass; checks use saved fitting-window evidence."
        ),
    ],
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Save project-specific checks. Each check has metric (r_hat_max, mae, rmse, wape), maximum and required. WAPE is a fraction. No default thresholds are assumed."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/quality-policies",
        {"name": name, "rationale": rationale, "checks": checks},
    )


async def evaluate_study_run(
    run_id: str,
    policy_id: Annotated[
        str, Field(description="Exact quality policy identifier to pin to the run or evaluation.")
    ],
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Save a quality report from existing evidence. Missing evidence never passes. Current predictive metrics cover the fitted window, not holdout."""
    return await _client(ctx).workflow_request(
        "POST", f"/study-runs/{run_id}/evaluations", {"policy_id": policy_id}
    )


async def list_study_evaluations(
    run_id: str,
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
    """Read preserved quality reports and evidence hashes."""
    payload = await _client(ctx).workflow_request("GET", f"/study-runs/{run_id}/evaluations")

    return page(payload, "evaluations", limit, offset)


async def list_study_decisions(
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
    """Read analyst decisions and agent recommendations."""
    payload = await _client(ctx).workflow_request("GET", f"/studies/{study_id}/decisions")

    return page(payload, "decisions", limit, offset)


async def recommend_study_run(
    study_id: Annotated[
        str,
        Field(
            description="Identifier of the existing study; project permissions are checked by Simba."
        ),
    ],
    run_id: str,
    evaluation_id: str,
    reason: Annotated[
        str, Field(description="Human-readable rationale retained in the study history.")
    ],
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Record a recommendation with evidence. This does not accept or promote a model; analyst acceptance happens in the frontend."""
    return await _client(ctx).workflow_request(
        "POST",
        f"/studies/{study_id}/decisions",
        {"run_id": run_id, "evaluation_id": evaluation_id, "action": "recommend", "reason": reason},
    )


def register(mcp: MCPServer) -> None:
    mcp.tool(
        title="List quality policies",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(list_quality_policies)
    mcp.tool(
        title="Create quality policy",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )(create_quality_policy)
    mcp.tool(
        title="Evaluate study run",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )(evaluate_study_run)
    mcp.tool(
        title="List study evaluations",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(list_study_evaluations)
    mcp.tool(
        title="List study decisions",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(list_study_decisions)
    mcp.tool(
        title="Recommend study run",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )(recommend_study_run)
