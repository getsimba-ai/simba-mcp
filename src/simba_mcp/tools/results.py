"""Results tools backed by the Simba API."""

from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from ..auth import _client
from ..runtime import AppContext

_CURVE_SECTIONS = ("response_curves", "marginal_curves")
_BAND_SUFFIXES = ("_lower_50", "_upper_50", "_lower", "_upper")


def _norm_channel(name: str) -> str:
    """Normalize a channel identifier for matching: lowercase, spaces to
    underscores, and strip the _activity/_spend suffix (results are keyed by
    activity-column name)."""
    k = str(name).strip().lower().replace(" ", "_")
    for suffix in ("_activity", "_spend"):
        if k.endswith(suffix):
            k = k[: -len(suffix)]
            break
    return k


def _column_channel(col: str) -> str:
    """Base channel of a curve column, with any credible-band suffix removed."""
    for suffix in _BAND_SUFFIXES:
        if col.endswith(suffix):
            col = col[: -len(suffix)]
            break
    return _norm_channel(col)


def _downsample(records: list, max_points: int) -> list:
    """Stride a grid-record list down to <= max_points, keeping first and last."""
    n = len(records)
    if max_points < 2 or n <= max_points:
        return records
    idx = {round(i * (n - 1) / (max_points - 1)) for i in range(max_points)}
    return [records[i] for i in sorted(idx)]


def _filter_results(payload: dict, channels: list | None, max_grid_points: int | None) -> dict:
    """Client-side channel filter + curve downsampling on a results payload.

    Applies only where channel identity is unambiguous. `contributions` is
    passed through untouched: its non-channel columns (controls, Base,
    Seasonality, ...) cannot be reliably told apart from unrequested channels.
    """
    target = payload.get("results") if isinstance(payload.get("results"), dict) else payload
    wanted = {_norm_channel(c) for c in channels} if channels else None

    for section in _CURVE_SECTIONS:
        recs = target.get(section)
        if not isinstance(recs, list):
            continue
        if wanted is not None:
            recs = [
                {k: v for k, v in r.items() if k == "Spend" or _column_channel(k) in wanted}
                for r in recs
            ]
        if max_grid_points:
            recs = _downsample(recs, max_grid_points)
        target[section] = recs

    if wanted is not None:
        for section in ("decay_curves", "saturation"):
            entry = target.get(section)
            sub = (
                entry.get("channels")
                if section == "saturation" and isinstance(entry, dict)
                else entry
            )
            if isinstance(sub, dict):
                filtered = {k: v for k, v in sub.items() if _norm_channel(k) in wanted}
                if section == "saturation":
                    entry["channels"] = filtered
                else:
                    target[section] = filtered
        for section, key in (("channel_summary", "Channel"), ("coefficients", "Channel")):
            recs = target.get(section)
            if isinstance(recs, list):
                target[section] = [r for r in recs if _norm_channel(r.get(key, "")) in wanted]
        mroi = target.get("mroi_summary")
        if isinstance(mroi, dict) and isinstance(mroi.get("channels"), list):
            mroi["channels"] = [
                r for r in mroi["channels"] if _norm_channel(r.get("channel", "")) in wanted
            ]
        # Per-period series (#591): channels x periods rows — the largest
        # per-channel section, so the filter matters most here.
        periods = target.get("mroi_periods")
        if isinstance(periods, dict) and isinstance(periods.get("rows"), list):
            periods["rows"] = [
                r for r in periods["rows"] if _norm_channel(r.get("channel", "")) in wanted
            ]
    return payload


async def get_model_results(
    model_hash: str,
    sections: str = "",
    format: str = "json",
    channels: list[str] | None = None,
    max_grid_points: int | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Get results from a completed model.

    Available sections:
    - channel_summary: per-channel aggregates {Channel, Sales, Spend, Revenue, ROI}.
    - contributions: per-period decomposition (Date, one column per channel, plus
      Base, Seasonality, Event Effect, Model, Fit Actual, Actual). Values are in
      KPI/unit space — the multiplier is NOT applied. Use `coefficients` for
      per-period revenue. Multiplicative (link="log") models fitted with the
      removal_lift attribution convention add an `Overlap` column: a negative
      shared-synergy reconciliation term so that
      Base + components + Overlap = Model. Overlap is NOT a channel — never
      rank it, share it, or feed it to the optimizer/scenarios. Overlap
      requires BOTH link="log" AND attribution="removal_lift" (the API
      default): under aumann_shapley (the dashboard default for
      multiplicative models since #509), shapley, or
      proportional_normalized, the interaction is allocated across
      components, which close exactly with NO Overlap column — its absence
      does NOT mean the model is additive or predates the feature.
      Control columns are measured against the reference point resolved at
      fit time (#452, see model_config.control_references) — e.g. "vs.
      average conditions" for a control that never reaches zero — not
      necessarily against zero, so a referenced control's series
      legitimately spans zero.
    - coefficients: per-period per-channel media results table (Date, Channel,
      Sales, Revenue, Spend, Media Units, ROI, Cost/Revenue/Sales per Media Unit).
      This is the only per-period revenue-space decomposition.
    - params: fitted posterior means per channel (alpha, decay, cpu, scalars).
    - decay_curves: adstock decay per channel (mean/lower/upper, l_max,
      adstock_type, curve points; dual-geometric models add decay_slow_* and
      dual_weight_* parameters).
    - response_curves: 100-point spend-vs-revenue grid per channel with credible
      bands ({ch}, {ch}_lower, {ch}_lower_50, {ch}_upper_50, {ch}_upper).
    - marginal_curves: same grid for marginal ROI (diminishing returns).
    - saturation: fitted saturation family and parameters (saturation_type is
      tanh, michaelis_menten, negative_exponential, or generalized_log;
      per-channel alpha/scale, plus transform_order and — for generalized_log
      only — per-channel sat_shape).
    - mroi_summary: headline marginal ROI at current spend per channel with a
      94% HDI (channel, current_spend, mroi_median, mroi_hdi_3, mroi_hdi_97).
      Post-#591 posterior fits add two averaging-convention scalars per
      channel — mroi_allperiods_unweighted_median (+_hdi_3/_hdi_97) and
      mroi_spendweighted_active_median (+_hdi_3/_hdi_97), with *_profit_*
      variants on margin models — plus a top-level conventions_available
      array. Channels with no active periods omit the spendweighted fields.
      Post-#629 fits also carry a *_mean beside every *_median (mroi_mean,
      mroi_profit_mean, pv_kernel_mass_mean, and the convention variants).
      The median is what the product displays; the mean is the statistic that
      reconciles with the marginal-revenue curve, since derivative and mean
      commute and median does not. Absent on anything fitted before #629 —
      there is no backfill, so feature-detect rather than assume.
    - mroi_periods: OPT-IN ONLY (#591) — never in the default payload;
      request it by name in `sections`. Per-period marginal ROI series:
      {available, hdi_prob, evaluation_point: "historical_period_spend",
      rows} with one row per (channel x modelled period): channel, date,
      spend, mroi_median/_hdi_3/_hdi_97, and mroi_profit_* on margin models.
      Models fitted before the artifact existed return
      {available: false, reason: "fitted_before_mroi_periods"} — refit to
      enable. Large (channels x periods) — pair with the channels filter.
    - model_stats: fit diagnostics (R², MAPE, Durbin-Watson, Max R_hat, ...).
    - actual_vs_model: actual vs predicted per period with 50%/95% HDIs.
    - long_run_rollup: MMM short-term + VAR long-run revenue rollup per channel;
      returns {available: false, reason: "no_linked_var_model"} when no VAR
      model is linked to this MMM. Joins by exact name unless the link declared
      a channel_map (see link_var_model) — mapped rows carry var_group and an
      allocated elasticity slice, with group-level truth in metadata.groups. A
      computed rollup where nothing joined stays available: true but carries
      reason: "no_channel_overlap" — check metadata.coverage, then declare a
      channel_map on the link.
    - optimizer: latest optimization results (see get_optimizer_results).
    - predictions: latest scenario prediction rows (see get_scenario_results).
    - posterior: full posterior summary table — one row per model variable
      with mean, sd, hdi_3%, hdi_97%, and r_hat (quotable 94% HDIs and
      per-variable convergence).
    - posterior_transforms: the importable transform-parameter posterior grid
      (what the dashboard's prior builder imports): per-channel alpha mean/sd,
      decay 94% HDI, dual-weight mean/sd, decay-slow HDI, sat-shape mean/sd,
      and the adstock structure including tied-group member aliases. Rows key
      on activity-column names — join via channel_map.
    - r_hat: per-parameter R-hat over ALL posterior variables — including
      transform RVs such as {channel}_decay that the posterior summary's
      coefficient rows do not cover. Use it to attribute a bad Max R_hat
      (model_stats) to a specific parameter block.
    - financials: the model's operating margin ({operating_margin,
      operating_margin_series}); omitted entirely for marginless models.
      operating_margin_series is a DATE-STRING-KEYED DICT
      ({"2024-01-01": 0.18, ...}), not a list of records.
    - cohort_ledger: per-(channel, source-period) forward-allocation ledger —
      each period's spend is credited with the future effects its adstock
      carryover earns (horizon slices plus PV-discounted financials from the
      fit-time cohort kernels). Models fitted before the artifact existed
      return {available: false, reason: ...} — feature-detect on `available`.
    - model_config: the resolved model specification (inputs, not posteriors)
      to audit or reconstruct the create_model call — includes config flags
      such as saturation_type, transform_order, and link ("log" =
      multiplicative). Multiplicative models with controls also report
      control_references (#452): per control, the requested and resolved
      attribution reference mode, the zero_distance diagnostic behind the
      "auto" choice, and the posterior-mean q_ref. Models created before
      these fields existed may omit them.
      priors_resolved reports what the fit actually consumed (#643): per row,
      overridden_fields lists only the fields that took effect, and
      accepted_not_used — present only when non-empty — names any that were
      accepted but inert for this model's configuration, each with a reason.
      A prior field can be spelled correctly and still do nothing: theta_*
      needs adstock_type "delayed", dual_weight_* needs "dual_geometric",
      sat_shape_* needs saturation_type "generalized_log", and the decay /
      half-life bounds are ignored FOR "dual_geometric". If a prior you set
      appears to have had no influence, read accepted_not_used first. The
      folded coordinates (half_marginal_*, effect_at_avg_*) are never called
      inert — they land in the row's scalars/alpha_sd/mean/sd.
    - channel_map: canonical identifier mapping, one record per channel:
      {channel, activity_column, spend_column} as configured at create time.
      This is the join key between channels[].name and the sections keyed by
      activity-column name (contributions, decay_curves, posterior_transforms).

    The response envelope includes `sections_available` — trust it over any
    hardcoded list if the server is newer than these docs.

    IMPORTANT — channel naming: results are keyed by the channel's ACTIVITY
    COLUMN name (e.g. "search_activity"), not by the `channels[].name` passed to
    create_model. These exact keys (case- and space-sensitive) must be used in
    run_optimizer bounds, laydown_weights, and period_cpm. Always read
    channel_summary first to get the exact keys.

    NOTE: Date values in contributions/coefficients records are millisecond
    epoch integers.

    CONTEXT-SIZE TIP: a full pull is very large (curve sections alone are 100
    grid points x channels x 5 band columns). In conversational use, request
    only the sections you need and pass channels=[...] and max_grid_points=20.

    Args:
        model_hash: The model hash.
        sections: Comma-separated list of sections to include.
                  Leave empty for all sections.
                  Common: "channel_summary,model_stats" for ROI and diagnostics.
        format: "json" (default) or "csv". CSV returns
                {"format": "csv", "content": "..."} — concatenated
                "# section" + CSV blocks, useful for saving to disk.
                Filtering below applies to JSON only.
        channels: Optional channel filter (matching is case/space-insensitive
                  and tolerates the _activity/_spend suffix). Applied to curve
                  sections, decay_curves, saturation, channel_summary,
                  coefficients, mroi_summary, and mroi_periods rows.
                  `contributions` is never filtered (its control columns are
                  indistinguishable from channels client-side).
        max_grid_points: Optional cap on response/marginal curve grid points;
                         records are strided evenly, keeping first and last.
    """
    res = await _client(ctx).get_model_results(model_hash, sections=sections, fmt=format)
    if format != "json" or (channels is None and max_grid_points is None):
        return res
    if not isinstance(res, dict) or res.get("_status_code", 200) >= 400:
        return res
    return _filter_results(res, channels, max_grid_points)


def register(mcp: MCPServer) -> None:
    mcp.tool()(get_model_results)
