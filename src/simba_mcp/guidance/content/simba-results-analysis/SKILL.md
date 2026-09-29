---
name: simba-results-analysis
description: Read saved Simba results, ROI and diagnostics.
metadata:
  version: "15"
---

# Analyse saved results

Use any supplied model identifier directly in get_model_results. Do not call
list_models or another discovery/status tool first: the result read checks the
identifier. Discover only if no identifier was supplied or that read rejects it,
and only when discovery is authorised.

Choose sufficient sections:
- Revenue/ROI: channel_summary; coefficients for individual periods.
- Diagnostics: model_stats,r_hat as required by the question.
- Decomposition: contributions, model_config and channel_map. Verify which
  components are media before classifying them; names alone are insufficient.
- Current/historical marginal ROI: mroi_summary/mroi_periods respectively.
- Add channel_map for unverified identity or media classification.

Use requested dates, never guessed bounds/year. Inspect dated rows when needed.
Before answering, identify every requested output, including combined totals as well
as individual values. Supply each once; check none is missing. Keep the requested
explanation within 100 words unless more detail is requested or needed for coverage.
Check that each formula describes the metric it labels; omit unrelated formulas.
Stop once answered: no unsolicited methodology, tool-use or safety footer.
Before sending, check every explanatory clause against a returned field,
a shown calculation or the documented contract. Remove plausible but unestablished
interpretations. If actions are explicitly requested, check the actual call record,
including refused attempts; never reconstruct motives.

Apply [interpretation](references/interpretation.md); consult the
[full contract](references/tool-reference.md) for other sections/parameters.
