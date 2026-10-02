---
name: simba-campaign-workflow
description: Inspect campaign facts, mapping, incremental evidence, conditional budgets and experiment screening.
metadata:
  version: "22"
---

# Investigate campaigns

Use this Skill for campaign performance, mapping, daily-equivalent suggestions or
experiment screening on an existing model. Marketer, reviewer and full profiles
can read these workflows. Mapping writes require marketer or full and explicit intent.

1. Start with the known model and observation window. Inspect [facts and attribution](references/workflow.md).
2. Preserve exact platform/account/campaign/ad-set and model-channel identity, currency,
   source versions and uncertainty. Platform-attributed conversions are not incremental lift.
3. For a mapping change, read [replacement and recovery](references/mapping.md).
4. For bounded budget suggestions, read [marginal evidence and budgets](references/budgets.md).
5. For screening experiment opportunities, read [priorities](references/experiments.md).
6. Stop on missing or incompatible evidence. A recommendation does not authorise spend,
   a fit, test creation, a new pipeline or an advertising-platform change.

Exact calls and observable synthetic evidence: [facts examples](references/workflow-examples.md),
[mapping examples](references/mapping-examples.md), [budget examples](references/budgets-examples.md)
and [experiment examples](references/experiments-examples.md).
