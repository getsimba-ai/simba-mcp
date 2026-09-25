---
name: simba-mmm-workflow
description: End-to-end Simba MMM workflow over MCP — upload a dataset, create and poll a Bayesian model, and read results correctly (section semantics, channel naming, attribution/Overlap rules, context-size controls). Use when building or analyzing an MMM through the Simba MCP tools.
---

# Simba MMM workflow (upload → create → poll → results)

## 0. Discover and plan

Call `get_backend_capabilities` first. Treat absent fields as unknown, not as
support. Model families available outside Studies may differ from study launch.
For study work, inspect existing recipes, policies and attempt/concurrency budgets.
Validate before freezing; optionally bind the returned content hash when saving.
After an uncertain launch reuse the exact submission key and inputs. Writes are
not automatically retried; inspect existing objects before repeating other writes.
On revision conflict reload and reconcile. A new key can spend another attempt.
Quality evaluations use saved fitted-window evidence; missing diagnostics do not
pass and analyst acceptance remains in the frontend. Poll after cancellation until
the backend confirms the final state.

### Studies: where each concern belongs

A study separates five things. Put each in its own place and do not repeat it
elsewhere. `question` and `context` are shown to people and never executed.

- **question** (`create_study` / `update_study`): what to find out, one or two sentences.
- **context** (same tools, optional): scope, assumptions, data caveats. Interpretation only.
- **recipe revision** (`create_study_recipe` / `revise_study_recipe`): how a model is built. Immutable per revision.
- **quality policy** (`create_quality_policy`): every acceptance check, threshold and required manual review. The only place rules live; evaluations run against the policy a run was launched under.
- **run settings** (`max_attempts`, `max_concurrent`, `state`): how many fits, how many at once, whether new fits may start.

Correct: question "Which channels drive weekly sales after price and seasonality, and
how stable are those estimates?"; context "UK only, 2022-01 to 2024-12; distribution
data missing for Q3 2023"; policy rules r_hat <= 1.2, holdout MAPE <= 15 %, manual
review of channel signs; max_attempts 8.
Incorrect: question "Build a 22-channel weekly model, train 2022-2024, validate on
2025 Q1, r_hat must be <= 1.2, at most 8 fits." Nothing enforces any of that: launch
reads only the run settings and evaluation reads only the policy.

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

## 1. Upload

1. Call `get_data_schema` first and validate the CSV against it — especially
   `x-simba-constraints.min_rows` and the media naming rule
   `{channel}_activity` / `{channel}_spend`. Inactive periods are `0`, never
   blank/NA. CSV only, 10 MB max.
2. `upload_data` with `csv_path` when the server runs locally (stdio) —
   large files must not transit the conversation. On hosted servers pass
   `csv_content`. The response's `warnings` field is authoritative on row
   sufficiency.
3. `list_uploads` / `get_upload` recover past uploads; `get_upload`'s
   `columns` ([{name, dtype}]) is enough to build `create_model` arguments
   without re-reading the CSV.

## 2. Create

- Minimal call: `uploaded_file_id`, `date_column`, `kpi_column`,
  `hierarchy_column` (exactly 1 unique value), `channels`
  ([{name, activity_column, spend_column}]).
- Decide **at create time** if profit analysis is ever wanted: pass
  `operating_margin` (scalar fraction) or `operating_margin_column`. These
  are TOP-LEVEL parameters — a margin placed inside a config dict is
  silently ignored and the model fits marginless. Without a stored margin,
  `financials` never appears and every profit optimization must re-supply
  `forward_margin`.
- Multiplicative form: `link="log"`; attribution conventions other than
  `removal_lift` require it. Priors: see the `simba-prior-conventions`
  skill before overriding anything.
- The response is a `model_hash` immediately — fitting is async.

## 3. Poll

- `get_model_status` until `complete` or `failed`. Fits take minutes to
  tens of minutes; poll with backoff, don't spin.
- On `failed`: `get_model` returns the error message plus the full config
  echo (it works for every status). Fix the config and re-create;
  `delete_model` cleans up the failed entry (failed-only; destructive).
- Models start unsaved (invisible to default `list_models`) — `save_model`
  files them into a project; `rename_model` names without saving.


If the backend returns `fit_liveness`, use its heartbeat age and configured
threshold to describe liveness separately from fit progress. The threshold
countdown is not completion ETA or an exact termination time. An absent field
or `available: false` means unknown liveness, not a healthy or stalled fit.
An exceeded threshold does not itself change model status. Poll with backoff;
do not automatically restart or duplicate a fit based on this metadata.


## 4. Read results correctly

- **Channel naming**: results are keyed by ACTIVITY-COLUMN name, not
  `channels[].name`. Always read `channel_summary` (or `channel_map`, the
  canonical join table) before quoting or re-using channel keys.
- **Context size**: a full pull is huge. Request only needed `sections`,
  pass `channels=[...]` and `max_grid_points=20` in conversational use.
- **Section semantics** (the docstring's per-section list is the API doc):
  `contributions` is KPI/unit space (multiplier NOT applied);
  `coefficients` is the per-period revenue table; `posterior` quotes 94%
  HDIs (`hdi_3%`/`hdi_97%` — never call it a 95% CI); `model_stats` Max
  R-hat > 1.2 means not converged (attribute it with the `r_hat` section).
- **Overlap**: appears only when `link="log"` AND
  `attribution="removal_lift"` (the API default; the dashboard default is
  aumann_shapley since #509, which closes exactly without it —
  pass `attribution="aumann_shapley"` at create time to reconcile with a
  dashboard-built model). Overlap is a
  reconciliation term, NOT a channel — never rank/share/optimize it, and
  never read its absence as "additive model".
- Trust the response's `sections_available` over any hardcoded list, and
  feature-detect optional artifacts (`mroi_periods`, `cohort_ledger`,
  post-#629 `*_mean` keys) — older fits simply lack them; there is no
  backfill.

For explicit control transforms/priors use `control_priors` as documented in
`../simba-prior-conventions/SKILL.md`; verify the effective configuration after
creation. An unsupported capability must not be bypassed by dropping settings.

## Re-evaluating a run

Preview first: `evaluate_study_run(..., preview=true)` shows what the assessment would contain and, for each custom check without a value now, whether an earlier assessment of the same run can lend its value (`carry_forward_available`) or why not (`carry_forward_blocked.why`). Carry forward only what the preview lists, from that assessment id; supply anything else yourself with method and source. Manual sign-off is never carried; a person renews it in the app. Each report is complete on its own and a newer sparse report never replaces an earlier enriched one.
