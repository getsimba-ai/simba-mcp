---
name: simba-data-reporting
description: Report actual KPI and spend from an existing stored dataset, preserving declared roles and source identity.
metadata:
  version: "23"
---

# Report actual data

Use for actual sales/KPI and spend by window or grouping, including pipeline-ingested
datasets already stored as uploads. All four profiles expose the required reads.

1. Use a supplied dataset ID directly. If unknown, use `list_uploads`, then `get_upload`.
2. Inspect schema/declared roles when needed; never infer KPI meaning from a column name.
3. Read [reporting and recovery](references/workflow.md) before `get_data_report`.
4. Retain source/version/digest, units, aggregation and data_through. Actual data totals
   are separate from MMM attribution, platform conversions and forecast results.
5. Narrow oversized reads. Missing roles or unavailable data require a clarification
   or owner handoff, never an upload, pipeline refresh or model fit.

Follow [executable examples](references/workflow-examples.md) for complete synthetic
discovery/reporting and refusal/recovery paths.


If the task spans unfamiliar Simba domains and workflow routing is enabled,
recommend_workflow can suggest guidance and visible tools. Skip it for a clear
workflow or already-loaded guidance. Its recommendation never authorises actions;
on fallback continue normal selection without repeating the routing call.
