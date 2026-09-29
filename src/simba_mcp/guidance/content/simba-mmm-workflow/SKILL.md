---
name: simba-mmm-workflow
description: Build a Simba MMM from uploaded or pipeline data. Use for data preparation, model creation and fit recovery; use results guidance for existing-model questions.
metadata:
  version: "1"
---

# Build an MMM

1. For new data, call get_data_schema and validate exact columns, roles and row requirements. Read [building](references/building.md) before upload or creation.
2. Discover backend capabilities only for the operation being planned, such as a new model family or publication. Do not add discovery to simple existing-result questions.
3. Before overriding priors, read [priors](references/priors.md), including anchor pairing and effective-configuration checks.
4. Preserve requested settings. Stop on unsupported capabilities rather than removing them. Model fitting requires user authorisation and an agreed scope.
5. Poll with backoff. On uncertain writes reconcile existing state; never create another fit just because the response or heartbeat is late.
6. Check the returned configuration, diagnostics and limitations before interpreting output. A completed fit is not scientific acceptance.

For an existing model's results use the results topic via get_workflow_guidance if that Skill is not installed. Guidance does not grant permission to write.
