# get_model_results: full contract

<!-- Generated from the handler docstring by simba_mcp.reference. -->

Get results from a completed model.

Available sections:
- channel_summary: per-channel aggregates {Channel, Sales, Spend, Revenue, ROI}.
- contributions: per-period decomposition (Date, one column per channel, plus
  Base, Seasonality, Event Effect, Model, Fit Actual, Actual). Values are in
  KPI/unit space — the multiplier is NOT applied. Use `coefficients` for
  per-period revenue. Multiplicative (link="log") models fitted with the
  removal_lift attribution convention add an `Overlap` column: a balancing
  residual, which can have either sign when effects are signed, so that
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
  Preserve the requested mean or median explicitly; they are not interchangeable.
  The mean reconciles with the marginal-revenue curve, since derivative and
  mean commute and median does not. Absent on anything fitted before #629 —
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
- prediction_window: OPT-IN ONLY saved prediction-window actuals/model values.
  Request sections="prediction_window" (JSON or CSV); omitted by default.
  This is not certified untouched holdout evidence. For study-linked models,
  serving it appends an access audit event; channel/grid filters do not alter it.
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

DATE WINDOW: pass start / end (ISO dates, inclusive) and/or granularity
("native", "week", "month" or "quarter") to window contributions,
coefficients, actual_vs_model and channel_summary. The response then
carries `meta` (window, basis, data_through, aggregation rules,
not_windowed). channel_summary is RECOMPUTED for the window — ROI =
ΣRevenue/ΣSpend per channel, profit priced with each period's own margin —
never filtered or averaged. Bucketed rows carry period_start/period_end
instead of Date; per-unit ratios are recomputed from sums; bucketed
actual_vs_model drops the per-period predictive intervals (they cannot be
added). mROI is never summed: mroi_periods comes back as fitted and is
listed in meta.not_windowed. VAR models window actual_vs_model only. The
window covers the model's training period; for data outside it (or
columns the model did not use) use get_data_report.

CONTEXT-SIZE TIP: a full pull is very large (curve sections alone are 100
grid points x channels x 5 band columns). In conversational use, request
only the sections you need and pass channels=[...] and max_grid_points=20.

Explicit JSON channel/grid requests add `_mcp_selection` metadata describing
requested selection, changed sections, original/returned row counts and grid
sampling. Backend metadata and warnings remain unchanged. Alias collisions
retain every matching exact identifier and are disclosed; never combine them.
Unmatched aliases refer only to filterable sections. Empty channels and grid
limits below 2 retain existing no-op behaviour with a warning. Unfiltered and
CSV results are unchanged. Local filtering does not bound backend downloads.

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
    max_response_bytes: Optional UTF-8 JSON result byte ceiling after filtering.
        Oversize results return an actionable error, never partial evidence.
        Bounds MCP content, not the backend HTTP download.
    max_grid_points: Optional cap on response/marginal curve grid points;
                     records are strided evenly, keeping first and last.
    start: Optional window start (YYYY-MM-DD), inclusive.
    end: Optional window end (YYYY-MM-DD), inclusive.
    granularity: Optional "native", "week", "month" or "quarter".
