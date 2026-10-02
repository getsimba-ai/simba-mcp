"""Read-only native views over existing authoritative result tools."""

from typing import Any

from mcp.server.mcpserver import Context

from ..runtime import AppContext
from ..schemas import APIResult
from .results import get_model_results
from .scenarios import get_optimizer_results


async def show_response_curves(
    model_hash: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Show served response curves, bands and current spend in a native chart.

    Read-only. Returns the existing JSON unchanged on every client. Missing points
    are gaps; sparse legacy grids are disclosed. Current spend is not a recommended
    allocation. Requests fixed sections and never accesses prediction-window data.
    """
    return await get_model_results(
        model_hash,
        sections="response_curves,mroi_summary,channel_map,model_config",
        ctx=ctx,
    )


async def show_decomposition(
    model_hash: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Show served contribution time series in KPI units in a native chart.

    Read-only. Overlap is a separate reconciliation term, never a channel. The
    attribution convention is displayed where available. Returns the same useful
    JSON on clients without visual support. Never requests prediction-window data.
    """
    return await get_model_results(
        model_hash,
        sections="contributions,channel_map,model_config",
        ctx=ctx,
    )


async def show_optimizer_allocation(
    model_hash: str,
    run_id: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Show saved allocation spend and separate decision/comparison result tables.

    Read-only. Pass run_id to read a specific saved run; omission reads the latest
    model-level result. Decision Revenue/ROI never mixes with fitted-convention
    OptimizedEvalRevenue/ROI or HistoricalRevenue/ROI. No scientific calculations
    occur in the view. Returns existing JSON unchanged without visual support.
    """
    return await get_optimizer_results(model_hash, run_id=run_id, ctx=ctx)
