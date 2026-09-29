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
