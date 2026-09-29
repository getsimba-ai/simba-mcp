---
name: simba-results-analysis
description: Read saved Simba results, ROI and diagnostics.
metadata:
  version: "7"
---

# Analyse saved results

Use a supplied completed model identifier directly in get_model_results; discover
only if missing or rejected. No repeated startup preflights.

Choose sufficient sections:
- Revenue/ROI: channel_summary; coefficients for individual periods.
- Diagnostics: model_stats,r_hat as required by the question.
- Decomposition: contributions, plus model_config for attribution.
- Current/historical marginal ROI: mroi_summary/mroi_periods respectively.
- Add channel_map for unverified identity or media classification.

Use requested dates, never guessed bounds/year. Inspect dated rows when needed.
Return only the requested fields/format and explanations. Omit unsolicited tool
narration. If asked about actions, report the recorded order and evidence available
before each action, never a reconstructed motive.

Apply [interpretation](references/interpretation.md); consult the
[full contract](references/tool-reference.md) for other sections/parameters.
