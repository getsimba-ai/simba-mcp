# Campaign facts and attribution

Prerequisites: a known owned model, a human-registered campaign facts source and a
clear window. These reads work in marketer, reviewer and full/data_scientist.

Call `list_campaigns` for identity and declared mapping; page only when needed and
return next_cursor unchanged. `suggested_channel` is a hint, never an applied map.
Read `get_campaign_report` with explicit dates, grain, grouping and metrics. Use
model_hash for channel grouping. Retain unmapped spend, currency, as_of, data_through,
source_versions and meta.aggregation. An empty source requires app-owner inspection;
do not register or run a pipeline automatically. Narrow a report_too_large read.

Read `get_campaign_incrementality` separately when the question needs incremental
evidence. State the channel-grain assumption first: the model's channel factor scales
the platform's campaign split. This is not independent campaign causal measurement.
Retain factor_source, method, pending/ready/unavailable intervals and attribution basis.
Do not manufacture intervals or treat platform value as incremental revenue.

For 401/403 retain the permission refusal; for missing facts preserve missingness.
Never fit or mutate to repair a read. These operations create no mapping or budget.
See [complete synthetic jobs](workflow-examples.md) in native references, or request
section=workflow-examples through MCP fallback.
