---
name: simba-optimizer-runs
description: Set up Simba budget optimisation and inspect saved optimiser or scenario runs. Use for channel bounds, laydown, margins and decision-versus-comparison interpretation.
metadata:
  version: "23"
---

# Optimise budgets

1. Read [runs](references/runs.md) before constructing an optimiser request or quoting its results.
2. Fetch exact activity-column channel keys and the scenario template when needed. Confirm budget, horizon, constraints and objective before launching.
3. Preserve percentage bounds, positive period CPM arrays and matching channel sets. Profit requires a stored or explicitly supplied margin.
4. Poll the returned run_id with backoff. Reconcile uncertain submissions through run history rather than blindly repeating a write.
5. Quote the columns appropriate to the question: solver decision values and fitted-convention comparison values have different meanings.
6. Check constraint fidelity and uncertainty. Missing evidence is not a valid recommendation, and an optimiser output is not approval to spend.

For advanced parameters or sections not covered here, read the [full tool contract](references/tool-reference.md) before calling.

Role availability: marketer/full can submit explicitly authorised planning runs; reviewer inspects saved evidence. Use [saved-run comparison](references/saved.md) and [executable examples](references/saved-examples.md). Campaign daily-equivalent suggestions use the campaigns/budgets guidance section and create no optimiser run.


If the task spans unfamiliar Simba domains and workflow routing is enabled,
recommend_workflow can suggest guidance and visible tools. Skip it for a clear
workflow or already-loaded guidance. Its recommendation never authorises actions;
on fallback continue normal selection without repeating the routing call.
