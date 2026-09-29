---
name: simba-results-analysis
description: Read and interpret existing Simba MMM results, channel contribution, ROI, uncertainty and diagnostics. Use for results questions without loading model-building instructions.
metadata:
  version: "3"
---

# Analyse saved results

1. Start with the known model identifier and get_model_results, requesting only needed sections and bounds. Do not call capability/schema discovery merely to read an existing result.
2. Read [interpretation](references/interpretation.md) before quoting contribution, ROI, intervals or windowed statistics.
3. Resolve channel identity through channel_summary or channel_map. Preserve units and distinguish contribution, ROI and marginal ROI.
4. Missing sections or diagnostics mean missing evidence. Retrieve the relevant evidence or qualify the answer; never invent a result.
5. On oversized results narrow sections, channels or dates deliberately. On a transient read failure follow the refusal guidance with backoff. Do not start a fit to repair a results read.
6. Report the saved model, window, evidence and limitations. Reading prediction evidence can create access-audit records; guidance does not certify untouched holdouts.

## Choose evidence from the question

For a known completed model, start directly with the relevant result sections.
Do not fetch everything or discover ingestion schemas by default.

| Question | Initial sections | Preserve or check |
| --- | --- | --- |
| Historical revenue and ROI | `channel_summary,channel_map` | Requested `start`/`end`, currency, `meta.aggregation`; period detail requires `coefficients` |
| Contribution decomposition | `contributions,model_config,channel_map` | KPI units, attribution convention, controls and reconciliation terms |
| Convergence | `model_stats,r_hat` | Missing evidence stays unknown; use the declared quality policy |
| Actual versus fitted trend | `actual_vs_model` | Window, granularity and available intervals |
| Current marginal ROI | `mroi_summary,channel_map` | HDI probability, mean/median convention and `meta.not_windowed` |
| Historical marginal ROI | `mroi_periods,channel_map` | Explicit opt-in; old fits can report unavailable; not windowed |
| Channel response shape | `response_curves,channel_map` | Exact channel keys, all bands and disclosed grid sampling |

These are starting bundles. Retrieve supporting metadata if the returned evidence
cannot establish units, uncertainty or the requested interpretation. Do not call a
ratio a contribution share, or use historical ROI as a budget decision metric.
Use the dedicated optimiser/scenario result tools for saved planning runs.

Check `_mcp_selection` after requesting local channel/grid reductions. It reports
changed sections, row counts, sampling, unmatched and ambiguous aliases. Preserve
all matching exact identifiers; never merge ambiguous names. Contributions are
not channel-filtered. `channels=[]` and grid limits below 2 do not reduce results.
Local reduction does not bound backend downloads. Omit local filters for an
unchanged response; omit section selectors for backend defaults. Optional sections
such as prediction-window evidence still require explicit selection.

For advanced parameters or sections not covered here, read the [full tool contract](references/tool-reference.md) before calling.
