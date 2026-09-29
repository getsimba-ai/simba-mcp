# Interpret saved evidence

- Ground each answer in the returned values, explicit metadata and supplied context.
  Explicit definitions resolve uncertainty: do not later claim those definitions
  are missing. Distinguish what this response omits from what the model never saved.
  A projected absence does not establish storage history or the contents of unread
  sections. Report signed effects without inventing raw inputs or unique causes.
  Answer the requested question, then check every explanatory sentence against its
  evidence. Remove unsupported additions; qualify only what remains genuinely unknown.
- contributions is KPI space; coefficients is per-period revenue. Historical ROI,
  contribution and marginal ROI are different quantities. Preserve currency and units.
- The headline mroi_summary fields evaluate marginal returns at the declared
  point; default current spend is mean spend over active training periods, not
  the latest spend. Separately named averaging-convention fields can contain
  historical averages. Do not confuse these with the headline. Missing
  mroi_periods does not make historical revenue/ROI in coefficients unavailable.
- Use backend window aggregates: ROI is summed revenue divided by summed spend,
  never the average period ROI. Preserve meta.aggregation and meta.not_windowed.
  Do not sum marginal ROI or predictive interval endpoints. Bucketed predictions
  may lack intervals; do not fabricate them.
- Preserve declared interval probability and mean/median convention. Posterior
  HDIs are 94%; other sections declare their own bands. Missing diagnostics do not
  prove convergence or failure. Use the declared quality policy for acceptance.
- Overlap under log-link removal_lift reconciles the decomposition; it is not a
  channel and need not be negative with signed effects. Its absence does not
  establish an additive model. Preserve controls
  and attribution convention. Never label KPI contributions as currency.
- sections_available is response metadata, never a section to request. Read it
  from an ordinary results response. A listed selector does not prove its artefact
  is populated. Trust explicit available/reason fields. Older artefacts
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
