"""Scenarios tools backed by the Simba API."""

from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from ..auth import _client
from ..runtime import AppContext


async def run_optimizer(
    model_hash: str,
    total_budget: float,
    num_periods: int,
    gamma: float,
    currency: str,
    bounds: dict,
    laydown_weights: dict,
    period_cpm: dict,
    objective: str = "revenue",
    forward_margin: float | None = None,
    period_multiplier: list[float] | None = None,
    include_historical_effect: bool = True,
    enable_warm_start: bool = True,
    optimizer_engine: str = "slsqp",
    sigma_penalty: str = "std",
    group_bounds: list[dict] | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Run budget optimization on a completed model.

    Finds the optimal budget allocation across channels to maximize
    predicted revenue â€” or predicted PROFIT with objective="profit" â€”
    within the given constraints.

    PROFIT OBJECTIVE: objective="profit" requires a margin source. If the model
    was built with an operating margin, it is used automatically; otherwise you
    MUST pass forward_margin (e.g. 0.18 for an 18% margin) or the API returns an
    error. Result fields (Revenue, ROI, ExpectedResponse) are then on the profit
    basis.

    IMPORTANT:
    - Channel names must exactly match model results (case-sensitive, space-sensitive).
      Results are keyed by the channel's ACTIVITY COLUMN name (e.g. "search_activity"),
      not by the `channels[].name` passed to create_model.
      Call get_model_results with sections="channel_summary" first to get exact names,
      or use get_scenario_template to discover channel names and their average CPM values.
    - bounds values are percentages of total_budget (0-100), not currency amounts.
    - laydown_weights and period_cpm must be ARRAYS of length num_periods, not scalars.
      Wrong: {"TV": 10}. Correct: {"TV": [10, 10, 10, 10]}.
    - The same channel keys must appear in all three: bounds, laydown_weights, and period_cpm.
    - All period_cpm values must be positive (> 0).
    - laydown_weights per channel must sum to a positive value (weights are normalized internally).

    Returns 202 (async). Use get_optimizer_results to poll until status is "complete".

    Args:
        model_hash: Hash of a completed model.
        total_budget: Total budget in currency units.
        num_periods: Number of periods to optimize over (matches your planning horizon).
        gamma: Uncertainty-aversion weight on the outcome spread (the
               objective is mean - gamma * spread). 0.0 = maximize expected
               return only (most aggressive); higher values penalize
               uncertainty harder (more conservative). The dashboard
               typically uses values in the 0-0.1 range.
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
        objective: "revenue" (default) or "profit". See PROFIT OBJECTIVE above.
        forward_margin: Decimal margin in (0, 1], e.g. 0.18 = 18%. Only used with
                       objective="profit"; required when the model has no stored
                       operating margin.
        period_multiplier: Optional array of length num_periods converting KPI
                          units to revenue per period over the planning horizon
                          (mirrors the model's multiplier_column, e.g. price).
        include_historical_effect: Include carryover from historical spend in the
                                  predicted response (default True).
        enable_warm_start: Warm-start the optimizer from a previous solution
                          (default True).
        optimizer_engine: "slsqp" (hardened SLSQP, default) or "marginal"
                         (water-fill engine: allocates until every funded
                         channel shows the same marginal return; exact
                         profit-hurdle semantics and the tightest optimality
                         certificates, with automatic SLSQP fallback).
        sigma_penalty: How gamma penalizes outcome spread: "std" (default),
                      "variance" or "frozen" (advanced; smoother alternatives
                      for hard-to-converge runs - leave on "std" normally).
        group_bounds: Joint constraints over channel SETS (#570),
                     e.g. [{"name": "trade", "channels": ["TV", "Search"],
                     "lower": 40, "upper": 60}] with lower/upper in % of
                     total_budget (same convention as bounds). Groups must be
                     disjoint and jointly feasible with the members'
                     per-channel bounds. Presence forces the slsqp engine.
                     Results gain GroupBounds/GroupBoundsReport columns; a
                     BINDING group's members legitimately sit off the global
                     marginal (they share the group's shadow price).
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
    if objective != "revenue":
        payload["objective"] = objective
    if forward_margin is not None:
        payload["forward_margin"] = forward_margin
    if period_multiplier is not None:
        payload["period_multiplier"] = period_multiplier
    if not include_historical_effect:
        payload["include_historical_effect"] = False
    if not enable_warm_start:
        payload["enable_warm_start"] = False
    if group_bounds:
        # #570: additive-only, same hash-preservation rule as engine/penalty.
        payload["group_bounds"] = group_bounds
    # Engine + penalty (#502): additive-only so default payloads stay
    # byte-identical (server-side content-hash dedup stays valid).
    if optimizer_engine != "slsqp":
        payload["optimizer_engine"] = optimizer_engine
    if sigma_penalty != "std":
        payload["sigma_penalty"] = sigma_penalty
    return await _client(ctx).run_optimizer(model_hash, payload)


async def get_optimizer_results(
    model_hash: str,
    run_id: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Get budget optimization status and results.

    Without run_id: returns the MODEL-LEVEL optimizer state. Top-level keys:
    `optimizer_status` ("none"/"pending"/"under way"/"complete"/"failed"),
    `progress` + `progress_text` while running, and `results` when complete.
    This reflects the LATEST run on the model â€” a newer run overwrites it, so
    a poller can lose sight of the run it submitted.

    With run_id (run_optimizer's response includes it): fetches that specific
    run, immune to later runs. Top-level keys include `run_id`, `model_hash`,
    `status`, `created_at`, `label`, `inputs`, and `results`. Poll THIS form
    when you need to know whether your own run completed.

    Reading `results` rows â€” the columns come from DIFFERENT conventions and
    must not be treated as interchangeable:
    - `Revenue` / `ROI`: the optimizer's DECISION math â€” removal-lift
      counterfactual revenue at the allocated spend. This is what the solver
      optimized.
    - `OptimizedEvalRevenue` / `OptimizedEvalROI` and `HistoricalRevenue` /
      `HistoricalROI`: fitted-convention COMPARISON columns â€” the reconciled
      accounting view matching the model's Contributions panel. Same spend,
      different question; never mix them with `Revenue`/`ROI` in one summary.
    - `ObjectiveMarginal`: the decision-math marginal return at the optimum
      (the quantity the solver equalizes across unconstrained channels).
    - `MroiAtOptimized` / `MroiAtOptimizedHdi3` / `MroiAtOptimizedHdi97`:
      posterior mROI evaluated at the optimized spend (94% HDI bounds) â€” a
      DIFFERENT quantity from ObjectiveMarginal (they can differ by several
      times); quote the one matching the question asked.
    - Convergence / KKT certificate fields report solver health. All-None
      placeholder arrays (PeriodResponse etc.) are stripped server-side.

    Args:
        model_hash: Hash of the model that was optimized.
        run_id: Optional optimization run id from run_optimizer's response.
            Pass it to poll a specific run's status/results.
    """
    return await _client(ctx).get_optimizer_results(model_hash, run_id=run_id)


async def get_scenario_template(
    model_hash: str,
    periods_forward: int = 12,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Generate a forward-period scenario template from a completed model.

    Returns future dates pre-filled with values from 1 year prior,
    the list of media and control channels, and average cost-per-unit
    per media channel.

    IMPORTANT: Always call this before run_scenario or run_optimizer to discover:
    - Channel names (use these exact names in scenario_data, bounds, laydown_weights, period_cpm)
    - Average CPM per channel (avg_cpu_by_channel â€” use for period_cpm in run_optimizer)
    - Baseline activity values per channel (rows â€” use as starting point for scenarios)
    - Media vs control channel classification (variable_classification field)

    The response also includes: operating_margin (the model's stored margin, if
    set â€” useful for profit math), variable_transforms (per-variable transform
    metadata), periodicity, and start_date.

    WARNING: Template data may contain NaN or null values for channels without
    historical data. You MUST replace NaN/null with 0 before passing to run_scenario,
    otherwise the prediction will fail downstream.

    Args:
        model_hash: Hash of a completed model.
        periods_forward: Number of future periods to generate (default 12).
    """
    return await _client(ctx).get_scenario_template(model_hash, periods_forward)


async def run_scenario(
    model_hash: str,
    scenario_data: list[dict],
    spend_metadata: list[dict] | None = None,
    rebuild_model: bool = True,
    evaluate_holdout: bool = False,
    skip_slicing: bool = False,
    proxy_channels: list[dict] | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Run a "what-if" scenario prediction on a completed model.

    Takes a set of future period rows with channel activity values and
    predicts the KPI outcome. Use get_scenario_template first to get
    the expected format, channel names, and baseline values. Channel names are
    the activity-column keys from the template/results (e.g. "search_activity"),
    not the `channels[].name` passed to create_model.

    IMPORTANT: Before submitting, replace any NaN/null values in scenario_data with 0.
    The template from get_scenario_template may contain NaN for channels without
    historical data, which will cause the prediction to fail.

    This is async (returns 202 with status "pending"). Poll get_scenario_results
    until status is "complete" or "failed".

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
        evaluate_holdout: Evaluate the scenario against held-out actuals when the
                         scenario period overlaps observed data (default False).
        skip_slicing: Skip per-channel contribution slicing in the prediction
                     output â€” faster when only the KPI total is needed (default False).
        proxy_channels: Optional list of proxy-channel mappings, each mapping a
                       scenario channel to a fitted channel whose transforms it
                       borrows (for channels without their own history).
    """
    payload: dict = {"scenario_data": scenario_data}
    if spend_metadata:
        payload["spend_metadata"] = spend_metadata
    if rebuild_model:
        payload["rebuild_model"] = True
    if evaluate_holdout:
        payload["evaluate_holdout"] = True
    if skip_slicing:
        payload["skip_slicing"] = True
    if proxy_channels:
        payload["proxy_channels"] = proxy_channels
    return await _client(ctx).run_scenario(model_hash, payload)


async def get_scenario_results(
    model_hash: str,
    run_id: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Get scenario prediction results.

    Without run_id: returns the MODEL-LEVEL scenario state â€” status
    (pending/complete/failed) and, when complete, the full prediction data
    including predicted KPI per period, channel contributions, confidence
    intervals, and base components (intercept, seasonality, trend). This
    reflects the LATEST scenario on the model â€” a newer run overwrites it,
    so a poller can lose sight of the run it submitted.

    With run_id (run_scenario's response includes it): fetches that specific
    saved run, immune to later runs â€” keys include `run_id`, `model_hash`,
    `name`, `status`, `pinned`, `notes`, `tags`, `key_metrics`, timestamps,
    `inputs` (the submitted payload), and `results`. Poll THIS form when you
    need to know whether your own run completed, or to disambiguate
    back-to-back scenarios.

    NOTE: Failed scenarios return status "failed" with an error message in the
    JSON body (not an HTTP error). Always check the status field.

    Args:
        model_hash: Hash of the model the scenario was run on.
        run_id: Optional scenario run id ("scn_..."), from run_scenario's
            response or list_runs(artifact="scenario").
    """
    return await _client(ctx).get_scenario_results(model_hash, run_id=run_id)


async def update_run(
    artifact: str,
    model_hash: str,
    run_id: str,
    name: str = "",
    notes: str | None = None,
    tags: list[str] | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Rename / annotate a saved optimizer or scenario run.

    Runs are auto-named at creation (e.g. "$1.2M Â· 12mo Â· Jan 5");
    renaming makes run history carry the analysis ("holiday cut -10%",
    "stretch 130%"). Renaming permanently flips the run's auto_named flag
    to false so future auto-naming never overwrites it. Only the fields
    you provide are changed.

    Args:
        artifact: "optimizer" (run_id "opt_...") or "scenario" ("scn_...").
        model_hash: Hash of the model the run belongs to.
        run_id: The run's stable id from run history.
        name: New display name (non-empty when given; capped at 255 chars).
        notes: Free-text annotation. Omit to leave untouched; pass "" to
            clear.
        tags: Replacement tag list (max 20 tags, 64 chars each).
    """
    kwargs: dict = {}
    if name:
        kwargs["name"] = name
    if notes is not None:
        kwargs["notes"] = notes
    if tags is not None:
        kwargs["tags"] = tags
    return await _client(ctx).update_run(artifact, model_hash, run_id, **kwargs)


async def set_run_pinned(
    artifact: str,
    model_hash: str,
    run_id: str,
    pinned: bool,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Pin or unpin a saved optimizer or scenario run.

    Declarative and idempotent: setting the current state again is a
    no-op, so scripts can safely re-run it.

    Args:
        artifact: "optimizer" (run_id "opt_...") or "scenario" ("scn_...").
        model_hash: Hash of the model the run belongs to.
        run_id: The run's stable id from run history.
        pinned: Desired pin state.
    """
    return await _client(ctx).set_run_pinned(artifact, model_hash, run_id, pinned)


async def list_runs(
    artifact: str,
    model_hash: str,
    limit: Annotated[
        int,
        Field(
            description="Maximum records to return. Existing endpoint defaults apply; workflow lists allow 1-200, or null to preserve the full legacy response."
        ),
    ] = 50,
    offset: Annotated[
        int,
        Field(
            description="Zero-based record offset. Concurrent changes can shift page boundaries."
        ),
    ] = 0,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """List a model's saved optimizer or scenario run history.

    Returns {model_hash, runs, count, limit, offset}. Each run summary has:
    run_id, name, auto_named, pinned, notes, tags, status, error_details,
    progress fields while running, key_metrics (optimizer: total_budget,
    num_periods, gamma, predicted_revenue/roi, ...; scenario: num_periods,
    total_planned_spend, predicted_outcome, ...; null metrics are omitted â€”
    treat every key as optional), and created/started/completed timestamps.
    Ordering is pinned-first, then newest-first.

    CAVEATS:
    - `count` is the LENGTH OF THIS PAGE, not the total run count â€” page
      until a short page.
    - The optimizer objective ("revenue"/"profit") is NOT in the summary;
      fetch the specific run (get_optimizer_results with run_id) and read
      its `inputs` â€” profit runs carry `objective: "profit"` there, revenue
      runs omit the key.

    Use get_optimizer_results / get_scenario_results with a run_id to fetch
    a listed run's full inputs and results; update_run / set_run_pinned to
    curate it.

    Args:
        artifact: "optimizer" (run ids "opt_...") or "scenario" ("scn_...").
        model_hash: Hash of the model whose run history to list.
        limit: Page size (API clamps to 1-200; default 50).
        offset: Rows to skip (paging).
    """
    return await _client(ctx).list_runs(artifact, model_hash, limit=limit, offset=offset)


def register(mcp: MCPServer) -> None:
    mcp.tool(
        title="Run optimizer",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )(run_optimizer)
    mcp.tool(
        title="Get optimizer results",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(get_optimizer_results)
    mcp.tool(
        title="Get scenario template",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(get_scenario_template)
    mcp.tool(
        title="Run scenario",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )(run_scenario)
    mcp.tool(
        title="Get scenario results",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(get_scenario_results)
    mcp.tool(
        title="Update run",
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=True
        ),
    )(update_run)
    mcp.tool(
        title="Set run pinned",
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=True
        ),
    )(set_run_pinned)
    mcp.tool(
        title="List runs",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(list_runs)
