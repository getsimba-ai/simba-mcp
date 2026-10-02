---
name: simba-results-analysis
description: Read saved Simba results, ROI and diagnostics.
metadata:
  version: "22"
---

# Analyse saved results

Reuse guidance sections already supplied in context. Fetch only missing sections.

Use any supplied model identifier directly in get_model_results. Do not call
list_models or another discovery/status tool first: the result read checks the
identifier. Discover only if no identifier was supplied or that read rejects it,
and only when discovery is authorised.

Choose sufficient sections:
- Revenue/ROI: channel_summary; coefficients for individual periods.
- Diagnostics: model_stats and r_hat for a screening rule. If the question
  contrasts that screen with a coefficient or posterior summary, also request
  posterior before describing the summary. Do not infer the summary from r_hat
  names.
- Decomposition: contributions, model_config and channel_map. Verify which
  components are media before classifying them; names alone are insufficient.
- Current/historical marginal ROI: mroi_summary/mroi_periods respectively.
- Add channel_map for unverified identity or media classification.

Use requested dates, never guessed bounds/year. Inspect dated rows when needed.
When the answer names a channel, include channel_map in that same read.
Pass granularity only when the question asks for a calendar bucket. The
token is week, never weekly.
When the question names JSON fields, the answer is only that JSON object.
No prose before or after it. A requested section absent from the returned
results is not an unknown quantity. For availability, use false and reason
not_returned unless the payload already gave a documented reason. For
convergence, use unknown and reason not_returned. Null is only for a numeric
field the returned evidence does not establish.
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

Role availability: all profiles can inspect saved results and [native views with JSON fallback](references/visuals.md). [Executable view examples](references/visuals-examples.md) preserve missing points and KPI units. Campaign and actual-data reporting use their focused Skills or the campaigns/reporting guidance topics.
