# Interpret saved evidence

- Support every claim with returned evidence or supplied context. Honour explicit
  definitions; do not later call them unknown. Response omission proves neither
  storage history nor unread contents. For unknown quantities, leave the value
  null and say "not established by these results". Do not assert or rule out a
  value, sign or equality. Avoid "is neither ... nor ..." and "is not zero":
  those exclude possibilities, whereas missing evidence does not.
- Preserve units: contributions are KPI, coefficients revenue. Spend and revenue
  totals are separate sums. Only ROI divides summed revenue by summed spend.
  Window ROI is not defined as an unweighted average of period ROI, although the
  two calculations can coincide. Assert an actual numerical difference only
  after calculating both from returned period evidence; otherwise distinguish
  the definitions without claiming unequal values.
  Respect meta.aggregation and meta.not_windowed. Date filters do not select or
  aggregate mroi_periods rows: inspect the returned dates and select requested
  rows yourself. Do not sum mROI or HDI bounds.
- Headline mROI uses its declared evaluation point. Mean active-period spend is
  not latest spend. Historical mROI averages are valid under their declared
  convention and separate from headline mROI. Preserve mean/median,
  interval probability and availability. HDI endpoints are not necessarily
  equal-tailed quantiles, even when field names contain percentile numbers.
  Do not invent missing bands. Differences between summary statistics alone do
  not establish distribution shape, tail behaviour or causes.
- Apply the requested diagnostic rule. The r_hat section covers all posterior
  variables by contract, including transforms; coefficient-only summaries do not.
  Use that declared scope without inventing missing variables. Missing diagnostics
  prove neither
  convergence nor failure; completion is not scientific acceptance.
- Overlap reconciles log-link removal_lift, can have either sign and is not media.
  Absence does not prove additivity. Retain controls; signed effects do not reveal
  raw inputs or unique causes. Do not favour a raw-input direction from the sign
  without the necessary coefficient/reference evidence.
- In model_config.priors_resolved, overridden_fields lists fields that took
  effect; accepted_not_used lists accepted but inert fields and reasons. Honour
  these contract meanings instead of guessing or treating them as unknown.
- Honour available/reason and _mcp_selection warnings. sections_available is
  metadata, not a selector or proof of populated artefacts.
- Narrow oversize reads; never fit/mutate to repair one. Read prediction_window
  only when authorised and needed; access may be audited, not proof of a holdout.
