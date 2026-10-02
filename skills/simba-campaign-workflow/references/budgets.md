# Campaign marginal evidence and conditional budgets

All profiles can call `get_campaign_marginal_returns` and
`recommend_campaign_budgets`. Prerequisites: completed owned model, matching facts,
currency and curve provenance. Read the marginal response for the exact inclusive
window and campaign/adset level. Keep context_key, composite identity and reasons.

Campaign shapes inherit the fitted channel shape, rescaled by observed spend share
and relative efficiency. Current daily spend is observed spend divided by inclusive
days, not a configured platform budget or a daily forecast. Missing posterior marginal
evidence leaves uncertainty unavailable.

Supply exactly one budget source: explicit channel_daily_budgets in daily currency
units, or a saved optimizer_run_id for the same model with verified dates/currency.
Saved totals become flat daily equivalents, not a daily schedule. Pass the reviewed
expected_context_key; changed evidence refuses with 409. Inspect fresh evidence,
then obtain any changed decision before another calculation. Do not relax bounds,
change channel totals or invent platform floors to force feasibility.

The POST is a read-only calculation: no saved run, fit, posterior job, mapping or
platform-budget change. Preserve reason, feasible_range, constraints, assumptions,
minor-unit rounding and uncertainty status. Use section=budgets-examples for calls.
