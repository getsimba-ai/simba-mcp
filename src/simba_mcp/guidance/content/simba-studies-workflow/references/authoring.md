### Studies: where each concern belongs

A study separates five things. Put each in its own place and do not repeat it
elsewhere. `question` and `context` are shown to people and never executed.

- **question** (`create_study` / `update_study`): what to find out, one or two sentences.
- **context** (same tools, optional): scope, assumptions, data caveats. Interpretation only.
- **recipe revision** (`create_study_recipe` / `revise_study_recipe`): how a model is built. Immutable per revision.
- **quality policy** (`create_quality_policy`): every acceptance check, threshold and required manual review. The only place rules live; evaluations run against the policy a run was launched under.
- **run settings** (`max_attempts`, `max_concurrent`, `state`): how many fits, how many at once, whether new fits may start.

Keep model specification in the revision and checks in the quality policy.
Choose thresholds for the declared study; examples are not universal MMM limits.
Question/context text does not enforce launch budgets or acceptance rules.

### Reading a recipe

Every revision (`list_study_recipes` with `expand`, `get_recipe_revision`,
`validate_study_recipe`) carries a read-time `inspection` block. Check
`inspection.engine.state` before launching: `stale` means launch will be refused
until the revision is re-frozen (`refreeze_recipe_revision`). `settings.<key>.value`
is what the fit would use, with `status` `authored` or `default`; `effective.form_data`
is only what was authored. A prior field with status `inert` is not a bug in the
recipe: it is a value the current adstock or saturation choice never reads, and the
`reason` names the gate that would make it live. Do not edit it away unless the gating
setting changes too. Absent configuration classifies nothing.

`inspection.lineage` is the dataset the model was built from, as recorded: read
`display` (the line people see, e.g. "Retail weekly · v3 · verified") and `available`
(checked now for you; `false` with a `reason` means the recorded source is gone or changed,
so editing that recipe will need the dataset chosen again; `null` with `origin: null` means
the model predates capture and nothing is inferred). Quote `display`, never a pipeline's
current name.

### Starting a recipe from scratch

Three doors into a study, and none needs a fit before launch:

1. **Import a fitted or saved configuration.** `adopt_model_into_study` without
   `confirm` returns the import report (`editable` fully or partly,
   `settings.not_recorded`, `dataset.recorded`); with `confirm=true` it creates an
   executable `base_model` revision 1 and attaches the fitted result as an adopted
   run outside the attempt budget.
2. **Author a draft.** `get_recipe_draft_template` (optionally with an owned
   `uploaded_file_id` or `pipeline_version_id`) → `create_recipe_draft` →
   `publish_recipe_draft` → revision 1 of a new recipe → `launch_study_run` under a
   quality policy.
3. **A person saved one from the wizard** ("Save a recipe"). Read it like any other
   revision; `get_recipe_revision_authoring` returns the snapshot it was saved from.

Every door yields a revision that carries a snapshot, so every recipe can be edited
later without rebuilding it.

**Fresh data from a pipeline.** To build on the newest data, `run_pipeline` then poll
`get_pipeline_run` every few seconds until `status` is `succeeded`, and pass its
`version_id` as `pipeline_version_id`. If `run_pipeline` returns `run_in_progress`,
poll that `run_id` instead of starting another. `set_pipeline_schedule` keeps a
pipeline refreshed daily or weekly (a whole UTC hour); scheduled runs are polled the
same way.

### Editing a recipe

Edit in place, never overwrite. Walkthrough, no fit until the last step:

1. `get_recipe_revision_authoring(recipe_id, N)` → the snapshot (check
   `source_available`; when false, attach a dataset to the draft before publishing).
2. `create_recipe_draft(study_id, draft_id, name, snapshot,
   target={"recipe_id": ..., "base_revision_id": ...})`; the draft is now an edit
   session of that recipe; change the fields you mean to, preserve everything else.
3. `publish_recipe_draft(draft_id, expected_version, publication_id, reason,
   target={"recipe_id": ..., "expected_version": <recipe version you read>})` →
   revision N+1 of the same recipe, the base revision recorded as its source.
4. `diff_recipe_revisions(recipe_id, N, N+1)` states exactly what changed; quote it.
5. `launch_study_run` on the new revision.

On `412 stale_version` someone saved first: your draft and every edit are kept.
Re-read the recipe, then publish again with the new `expected_version` (revision
N+2), or drop `target` to branch into a new recipe. A multi-brand draft cannot
publish into one recipe (`409 target_requires_single_recipe`); publish it without a
target. Never "edit" by `revise_study_recipe` with a hand-built specification when a
snapshot exists; that discards the authored state.
