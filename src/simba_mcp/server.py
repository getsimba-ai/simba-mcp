"""
SIMBA MCP Server — exposes Simba's API v1 as MCP tools.

Tools allow AI assistants (Claude, Cursor, etc.) to interact with
Marketing Mix Models: upload data, create models, check status,
get results, and run budget optimizations.

Run locally:  simba-mcp
Run remote:   uvicorn "simba_mcp.server:create_app()" --host 0.0.0.0 --port 8100
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from .api_client import SimbaAPIClient

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    client: SimbaAPIClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    base_url = os.environ.get("SIMBA_API_URL", "http://localhost:5005")
    api_key = os.environ.get("SIMBA_API_KEY", "")
    if not api_key:
        logger.warning(
            "SIMBA_API_KEY is not set — all API calls will return an authentication error. "
            "This MCP server requires a Simba account. "
            "Book a call to get started: https://calendly.com/niall-oulton"
        )
    client = SimbaAPIClient(base_url, api_key)
    try:
        yield AppContext(client=client)
    finally:
        await client.close()


mcp = FastMCP(
    "Simba MMM",
    instructions=(
        "Simba is a Bayesian Marketing Mix Modeling (MMM) platform. "
        "Use these tools to upload marketing data, build MMM models, "
        "check fitting progress, retrieve results (channel ROI, contributions, "
        "model diagnostics), and run budget optimizations."
    ),
    json_response=True,
    stateless_http=True,
    lifespan=app_lifespan,
)


def _client(ctx: Context[ServerSession, AppContext]) -> SimbaAPIClient:
    return ctx.request_context.lifespan_context.client


# ---------------------------------------------------------------------------
# Tool 1: get_data_schema
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_data_schema(ctx: Context[ServerSession, AppContext]) -> dict:
    """Get the canonical CSV data schema for Simba MMM input files.

    Returns the JSON Schema specification describing required columns
    (date, KPI, multiplier, hierarchy), media channel column naming
    conventions ({channel}_activity, {channel}_spend), constraints
    (min rows, max file size), and supported date formats.
    """
    return await _client(ctx).get_schema()


# ---------------------------------------------------------------------------
# Tool 2: upload_data
# ---------------------------------------------------------------------------


@mcp.tool()
async def upload_data(
    csv_content: str,
    name: str = "",
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Upload a CSV dataset to Simba for use in model building.

    The CSV should follow the canonical schema: one row per time period
    with date, KPI, multiplier, hierarchy, media activity/spend columns,
    and optional control variables.

    Args:
        csv_content: The full CSV text content (not base64, just raw CSV text).
        name: Optional dataset name for identification.

    Returns the uploaded file ID (needed for create_model), row/column counts,
    and any validation warnings.
    """
    return await _client(ctx).upload_csv(csv_content, name)


# ---------------------------------------------------------------------------
# Tool 3: list_models
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_models(
    include_unsaved: bool = False,
    limit: int = 50,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """List all Marketing Mix Models for the authenticated user.

    Returns model name, hash, status (pending/under way/complete/failed),
    type (mmm/var), hierarchy value, and timestamps.

    Args:
        include_unsaved: Include draft/unsaved models (default false).
        limit: Maximum number of models to return (default 50, max 500).
    """
    return await _client(ctx).list_models(include_unsaved=include_unsaved, limit=limit)


# ---------------------------------------------------------------------------
# Tool 4: create_model
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_model(
    uploaded_file_id: int,
    date_column: str,
    kpi_column: str,
    hierarchy_column: str,
    channels: list[dict],
    multiplier_column: str = "",
    control_columns: list[str] | None = None,
    total_media_effect: str = "Other",
    priors: list[dict] | None = None,
    trend: bool = False,
    seasonality: bool = False,
    likelihood: str = "normal",
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Create and start fitting a new Bayesian Marketing Mix Model.

    This queues an async model fit and returns immediately with a model_hash.
    Use get_model_status to poll for progress until status is 'complete'.

    Priors are calculated automatically using smart defaults based on cost
    shares, industry benchmarks, and channel-type detection. You can
    override individual channels via the priors parameter.

    Args:
        uploaded_file_id: The file ID returned by upload_data.
        date_column: Name of the date column in the CSV.
        kpi_column: Name of the KPI/dependent variable column.
        hierarchy_column: Name of the brand/segment column (must have exactly 1 unique value).
        channels: List of channel definitions, each with keys: name, activity_column, spend_column.
                  Example: [{"name": "TV", "activity_column": "tv_grps", "spend_column": "tv_spend"}]
        multiplier_column: Column to convert KPI to revenue. Defaults to kpi_column.
        control_columns: Non-media control variable column names (e.g. ["price", "distribution"]).
        total_media_effect: Controls prior strength. Either an industry name for a benchmark
                           ("FMCG"=6%, "Retail"=9%, "TelCo"=30%, "Financial Services"=19%,
                           "E-Commerce"=22%, "Other"=12%) or a custom decimal like "0.15"
                           meaning "I believe all media drives 15% of my KPI". Default "Other".
        priors: Optional per-channel prior overrides. Each dict should have "channel" matching
                a channels[].name, plus any fields to override: distribution, mean, sd, lower,
                upper, transform, alpha_sd, decay_lower, decay_upper, adstock_type, scalars,
                effect_period. Only specified fields are overridden; the rest use smart defaults.
        trend: Enable dynamic baseline trend component.
        seasonality: Enable automatic seasonality detection.
        likelihood: Likelihood function ("normal", "studentt", "negbinomial").

    Returns the model_hash for status polling.
    """
    payload: dict = {
        "data_source": {"uploaded_file_id": uploaded_file_id},
        "date_column": date_column,
        "kpi_column": kpi_column,
        "hierarchy_column": hierarchy_column,
        "channels": channels,
        "control_columns": control_columns or [],
        "total_media_effect": total_media_effect,
        "config": {
            "trend": trend,
            "seasonality": seasonality,
            "likelihood": likelihood,
        },
    }
    if multiplier_column:
        payload["multiplier_column"] = multiplier_column
    if priors:
        payload["priors"] = priors

    return await _client(ctx).create_model(payload)


# ---------------------------------------------------------------------------
# Tool 5: get_model_status
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_model_status(
    model_hash: str,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Check the fitting progress of a model.

    Returns status (pending/under way/complete/failed), progress percentage,
    estimated time remaining, and timestamps.

    Args:
        model_hash: The model hash returned by create_model or list_models.
    """
    return await _client(ctx).get_model_status(model_hash)


# ---------------------------------------------------------------------------
# Tool 6: get_model_results
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_model_results(
    model_hash: str,
    sections: str = "",
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Get results from a completed model.

    Available sections: contributions, channel_summary, coefficients,
    params, optimizer, predictions, model_stats, decay_curves,
    response_curves, marginal_curves, actual_vs_model.

    Args:
        model_hash: The model hash.
        sections: Comma-separated list of sections to include.
                  Leave empty for all sections.
                  Common: "channel_summary,model_stats" for ROI and diagnostics.
                  Use "response_curves" for spend-vs-revenue curves per channel.
                  Use "marginal_curves" for diminishing returns curves.
                  Use "actual_vs_model" for model fit quality (actual vs predicted).
    """
    return await _client(ctx).get_model_results(model_hash, sections=sections)


# ---------------------------------------------------------------------------
# Tool 7: run_optimizer
# ---------------------------------------------------------------------------


@mcp.tool()
async def run_optimizer(
    model_hash: str,
    total_budget: float,
    num_periods: int,
    gamma: float,
    currency: str,
    bounds: dict,
    laydown_weights: dict,
    period_cpm: dict,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Run budget optimization on a completed model.

    Finds the optimal budget allocation across channels to maximize
    predicted revenue within the given constraints.

    IMPORTANT: Channel names in bounds, laydown_weights, and period_cpm must
    match the media channel names from get_model_results (channel_summary section).
    Use get_scenario_template to discover channel names and their average CPM values.

    All three dicts (bounds, laydown_weights, period_cpm) must have the same
    set of channel keys, and array values must have length equal to num_periods.

    Args:
        model_hash: Hash of a completed model.
        total_budget: Total budget in currency units.
        num_periods: Number of periods to optimize over (matches your planning horizon).
        gamma: Aggressiveness parameter (0 = conservative, 1 = aggressive).
               0.0 = maximize expected return only; 1.0 = heavily penalize uncertainty.
        currency: Currency code (e.g. "USD", "GBP").
        bounds: Per-channel min/max budget allocation as PERCENTAGES (0-100).
                Every channel must appear. Example:
                {"TV_Impressions": {"lower": 5, "upper": 40},
                 "Search_Clicks": {"lower": 10, "upper": 50}}
        laydown_weights: Per-channel spend timing weights. Each value is an array of
                        length num_periods. Weights are relative (normalized internally).
                        Use uniform [1, 1, ...] for even distribution across periods.
                        Example: {"TV_Impressions": [1, 1, 1, 1]}
        period_cpm: Per-channel cost-per-metric for each period. Each value is an array
                   of length num_periods with positive values. Get baseline CPM from
                   get_scenario_template (avg_cpu_by_channel field).
                   Example: {"TV_Impressions": [10.5, 10.5, 10.5, 10.5]}

    Returns immediately with status. Use get_optimizer_results to poll for results.
    """
    payload = {
        "total_budget": total_budget,
        "num_periods": num_periods,
        "gamma": gamma,
        "currency": currency,
        "bounds": bounds,
        "laydown_weights": laydown_weights,
        "period_cpm": period_cpm,
    }
    return await _client(ctx).run_optimizer(model_hash, payload)


# ---------------------------------------------------------------------------
# Tool 8: get_optimizer_results
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_optimizer_results(
    model_hash: str,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Get budget optimization status and results.

    Returns optimizer_status (pending/complete/failed) and, when complete,
    the full optimization results including per-channel budget allocation,
    predicted revenue, and ROI.

    Args:
        model_hash: Hash of the model that was optimized.
    """
    return await _client(ctx).get_optimizer_results(model_hash)


# ---------------------------------------------------------------------------
# Tool 9: get_scenario_template
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_scenario_template(
    model_hash: str,
    periods_forward: int = 12,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Generate a forward-period scenario template from a completed model.

    Returns future dates pre-filled with values from 1 year prior,
    the list of media and control channels, and average cost-per-unit
    per media channel.

    IMPORTANT: Always call this before run_scenario or run_optimizer to discover:
    - Channel names (use these exact names in scenario_data, bounds, laydown_weights, period_cpm)
    - Average CPM per channel (avg_cpu_by_channel — use for period_cpm in run_optimizer)
    - Baseline activity values per channel (rows — use as starting point for scenarios)
    - Media vs control channel classification

    Args:
        model_hash: Hash of a completed model.
        periods_forward: Number of future periods to generate (default 12).
    """
    return await _client(ctx).get_scenario_template(model_hash, periods_forward)


# ---------------------------------------------------------------------------
# Tool 10: run_scenario
# ---------------------------------------------------------------------------


@mcp.tool()
async def run_scenario(
    model_hash: str,
    scenario_data: list[dict],
    spend_metadata: list[dict] | None = None,
    rebuild_model: bool = True,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Run a "what-if" scenario prediction on a completed model.

    Takes a set of future period rows with channel activity values and
    predicts the KPI outcome. Use get_scenario_template first to get
    the expected format, channel names, and baseline values.

    This is async — returns immediately with status "pending".
    You MUST poll get_scenario_results afterwards to get the actual prediction output.

    Workflow: get_scenario_template -> modify values -> run_scenario -> poll get_scenario_results

    Args:
        model_hash: Hash of a completed model.
        scenario_data: Array of period rows, each a dict with "Date" (YYYY-MM-DD format)
                      and channel activity columns. Channel names must match exactly what
                      get_scenario_template returns in the "channels" field.
                      Example: [{"Date": "2025-01-06", "TV_Impressions": 50000, "Search_Clicks": 1200}]
        spend_metadata: Optional per-channel spend info for ROI calculation in results.
                       Each entry: {"channel": "TV_Impressions", "metric": "impressions",
                       "cpm": 25.0, "total_spend": 125000,
                       "weekly_spend": [25000, 25000, ...]}
        rebuild_model: Recompile the model graph before prediction. Must be True (default)
                      for API-initiated scenarios where the model graph is not in memory.
    """
    payload: dict = {"scenario_data": scenario_data}
    if spend_metadata:
        payload["spend_metadata"] = spend_metadata
    if rebuild_model:
        payload["rebuild_model"] = True
    return await _client(ctx).run_scenario(model_hash, payload)


# ---------------------------------------------------------------------------
# Tool 11: get_scenario_results
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_scenario_results(
    model_hash: str,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Get scenario prediction results.

    Returns status (pending/complete/failed) and, when complete,
    the full prediction data including predicted KPI per period,
    channel contributions, confidence intervals, and base components
    (intercept, seasonality, trend).

    Args:
        model_hash: Hash of the model the scenario was run on.
    """
    return await _client(ctx).get_scenario_results(model_hash)


# ---------------------------------------------------------------------------
# ASGI app for uvicorn deployment (lazy to avoid overhead in stdio mode)
# ---------------------------------------------------------------------------


def create_app():
    """Create the ASGI app for uvicorn/Streamable HTTP deployment."""
    mcp.settings.streamable_http_path = "/"
    return mcp.streamable_http_app()
