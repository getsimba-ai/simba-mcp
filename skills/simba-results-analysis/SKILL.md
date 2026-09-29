---
name: simba-results-analysis
description: Read saved Simba results, ROI and diagnostics.
metadata:
  version: "11"
---

# Analyse saved results

Use a supplied completed model identifier directly in get_model_results; discover
only if missing or rejected. No repeated startup preflights.

Choose sufficient sections:
- Revenue/ROI: channel_summary; coefficients for individual periods.
- Diagnostics: model_stats,r_hat as required by the question.
- Decomposition: contributions, model_config and channel_map. Verify which
  components are media before classifying them; names alone are insufficient.
- Current/historical marginal ROI: mroi_summary/mroi_periods respectively.
- Add channel_map for unverified identity or media classification.

Use requested dates, never guessed bounds/year. Inspect dated rows when needed.
Answer with the requested values and a brief explanation of each requested
distinction. Stop once answered: no unsolicited methodology, tool-use or safety
footer. Before sending, check every explanatory clause against a returned field,
a shown calculation or the documented contract. Remove plausible but unestablished
interpretations. If actions are explicitly requested, check the actual call record,
including refused attempts; never reconstruct motives.

Apply [interpretation](references/interpretation.md); consult the
[full contract](references/tool-reference.md) for other sections/parameters.
