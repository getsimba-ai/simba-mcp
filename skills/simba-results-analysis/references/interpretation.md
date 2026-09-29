# Interpret saved evidence

- contributions is KPI space; coefficients is per-period revenue. Historical ROI,
  contribution and marginal ROI are different quantities. Preserve currency and units.
- Use backend window aggregates: ROI is summed revenue divided by summed spend,
  never the average period ROI. Preserve meta.aggregation and meta.not_windowed.
  Do not sum marginal ROI or predictive interval endpoints. Bucketed predictions
  may lack intervals; do not fabricate them.
- Preserve declared interval probability and mean/median convention. Posterior
  HDIs are 94%; other sections declare their own bands. Missing diagnostics do not
  prove convergence or failure. Use the declared quality policy for acceptance.
- Overlap under log-link removal_lift reconciles the decomposition; it is not a
  channel. Its absence does not establish an additive model. Preserve controls
  and attribution convention. Never label KPI contributions as currency.
- Trust sections_available and explicit available/reason fields. Older artefacts
  can be unavailable. Retrieve supporting evidence or qualify the answer when
  units, uncertainty or provenance are absent.
- Explicit channel/grid filters add _mcp_selection. Check changed sections, row
  counts, sampling and ambiguous/unmatched aliases. Preserve exact matching keys;
  contributions are not filtered. Empty channels or grid limits below two do not
  reduce results. Local reduction does not bound backend downloads.
- On an oversize refusal, narrow the safe read deliberately. Never fit or mutate
  to repair a read. Request prediction_window only when specifically needed;
  its access can be audited and its values do not certify untouched holdout status.
- Use dedicated saved optimiser/scenario result tools for planning comparisons;
  preserve their decision versus fitted/evaluation metric conventions.
