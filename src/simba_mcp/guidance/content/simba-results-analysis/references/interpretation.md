## 4. Read results correctly

- **Channel naming**: results are keyed by ACTIVITY-COLUMN name, not
  `channels[].name`. Always read `channel_summary` (or `channel_map`, the
  canonical join table) before quoting or re-using channel keys.
- **Context size**: a full pull is huge. Request only needed `sections`,
  pass `channels=[...]` and `max_grid_points=20` in conversational use.
- **Section semantics** (the docstring's per-section list is the API doc):
  `contributions` is KPI/unit space (multiplier NOT applied);
  `coefficients` is the per-period revenue table; `posterior` quotes 94%
  HDIs (`hdi_3%`/`hdi_97%`; never call it a 95% CI); use `r_hat` and the declared quality policy when discussing convergence;
  missing diagnostics do not establish convergence.
- **Overlap**: appears only when `link="log"` AND
  `attribution="removal_lift"` (the API default; the dashboard default is
  aumann_shapley, which closes exactly without it;
  pass `attribution="aumann_shapley"` at create time to reconcile with a
  dashboard-built model). Overlap is a
  reconciliation term, NOT a channel; never rank/share/optimise it, and
  never read its absence as "additive model".
- **Date windows**: `get_model_results(start=, end=, granularity=)` windows
  the per-period sections and RECOMPUTES `channel_summary` for the window
  (ΣRevenue/ΣSpend, profit with each period's margin). Never compute a
  window ROI yourself by averaging per-period ROIs, and never sum mROI;
  read `meta.aggregation` for the rules applied.
- Trust the response's `sections_available` over any hardcoded list, and
  feature-detect optional artifacts (`mroi_periods`, `cohort_ledger`,
  `*_mean` keys); older fits simply lack them; there is no
  backfill.

## Selective reads and recovery

- For a historical ROI answer, request `channel_summary,channel_map` and the
  relevant inclusive date window. Add `coefficients` only when period-level
  evidence or reconciliation is needed. Read currency and aggregation metadata;
  if absent, qualify the answer or retrieve the supporting evidence.
- Never average period ROIs or marginal medians. For example, revenues 200 and
  300 on spends 50 and 150 imply total ROI 2.5, not the average period ROI of 3.
  Backend windowed aggregates remain the source of reported model statistics.
- A requested window does not change every section. Retain `meta.not_windowed`.
  Bucketed predictive intervals cannot be constructed by summing their endpoints.
- Channel/grid filtering is local JSON processing. `_mcp_selection` describes
  actual changes and retains backend metadata. Unmatched aliases mean no match
  in supported filterable sections, not proof a channel is absent from the model.
- An oversized-result refusal contains no partial analytical evidence. Narrow
  sections, channels or dates deliberately, then retry the safe read. Do not
  start a fit, write data, or access `prediction_window` as automatic recovery.
- Saved prediction-window access may create an audit event. Only request it when
  needed for the user's question, preserve provenance, and never certify an
  untouched holdout from the prediction values alone.
