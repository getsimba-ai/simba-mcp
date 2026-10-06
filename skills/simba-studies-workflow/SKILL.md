---
name: simba-studies-workflow
description: Author, edit and review Simba Studies, recipes, policies and runs. Use for immutable publication, launch recovery, diagnostics and human handoff.
metadata:
  version: "23"
---

# Work with Studies

1. Check operation-specific backend capabilities, the study, policy and attempt/concurrency budgets before authoring or launching.
2. Read [authoring](references/authoring.md) for import, draft publication, recipe inspection or edits. Preserve unedited snapshot fields and inspect revision diffs.
3. Read [recovery](references/recovery.md) before launch, cancellation or retry. Reuse the exact submission key and inputs after an uncertain launch; cancellation requested is not cancellation complete.
4. Read [review](references/review.md) before evaluating or recommending. Bind conclusions to the policy, immutable revision and saved evidence.
5. Missing diagnostics do not pass. In-sample fit does not establish holdout validation; declare validation requirements and provenance before using prediction evidence.
6. A recommendation is a handoff to a person. No acceptable candidate is a valid conclusion. Guidance cannot authorise acceptance or bypass budgets.

Role availability: all profiles inspect Studies evidence; reviewer/full can record authorised assessments/declarations/recommendations; authoring, policy changes and launches require full. [Missing-evidence example](references/review-examples.md) preserves not_evaluated and never claims promotion.


If the task spans unfamiliar Simba domains and workflow routing is enabled,
recommend_workflow can suggest guidance and visible tools. Skip it for a clear
workflow or already-loaded guidance. Its recommendation never authorises actions;
on fallback continue normal selection without repeating the routing call.
