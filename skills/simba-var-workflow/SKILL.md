---
name: simba-var-workflow
description: Build and inspect Simba VAR models and linked long-run MMM results. Use for long-term effects, VAR fit recovery and long-run rollup interpretation.
metadata:
  version: "2"
---

# Work with VAR models

1. Read [workflow](references/workflow.md) before configuring, linking or interpreting a VAR model.
2. Check the relevant model-family capability before a new creation or study launch. Preserve endogenous/exogenous variables and prior settings.
3. Agree fitting scope before launching and poll with backoff. Elapsed time or missing liveness evidence is not proof that a fit is stuck.
4. On failure inspect get_model; on an uncertain write reconcile existing state before repeating it.
5. Link only the intended compatible saved models. Feature-detect the long-run rollup and preserve exact channel identity.
6. A missing rollup is a reported state, not a zero long-term effect. MMM quality policies do not establish VAR scientific acceptance.
