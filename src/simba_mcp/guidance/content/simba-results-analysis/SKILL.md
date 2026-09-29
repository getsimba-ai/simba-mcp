---
name: simba-results-analysis
description: Read and interpret saved Simba results, contribution, ROI, uncertainty and diagnostics.
metadata:
  version: "6"
---

# Analyse saved results

When the user supplies a completed model identifier, use it verbatim in
get_model_results. It is already selected: do not call list_models, get_model,
get_model_status or ingestion/schema discovery to verify it. Discover models only
when the identifier is missing or the results endpoint explicitly rejects it.

Choose sections from the question:

- Revenue or ROI: channel_summary,channel_map; pass the requested start/end.
- Individual historical ROI periods: coefficients; these are not marginal ROI.
- Contribution decomposition: contributions,model_config; add channel_map for channel identity.
- Convergence: model_stats,r_hat.
- Current marginal ROI: mroi_summary,channel_map.
- Historical marginal ROI: mroi_periods; explicitly request this optional artefact.
- Trends or curves: actual_vs_model or the relevant curve section; add identity evidence as needed.

Use the smallest sufficient bundle, then answer. Missing evidence stays unknown.
Keep exact identifiers for subsequent tool arguments; display names are acceptable
in prose when channel_map verifies the relationship.

Read [interpretation](references/interpretation.md) for units, intervals and
windows. Read the [full contract](references/tool-reference.md) only for additional
sections or parameters. Preserve backend metadata and _mcp_selection warnings.
