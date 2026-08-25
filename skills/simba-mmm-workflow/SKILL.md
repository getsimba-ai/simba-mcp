---
name: simba-mmm-workflow
description: End-to-end Simba MMM workflow over MCP — upload a dataset, create and poll a Bayesian model, and read results correctly (section semantics, channel naming, attribution/Overlap rules, context-size controls). Use when building or analyzing an MMM through the Simba MCP tools.
---

# Simba MMM workflow (upload → create → poll → results)

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
  proportional_normalized, which closes exactly without it). Overlap is a
  reconciliation term, NOT a channel — never rank/share/optimize it, and
  never read its absence as "additive model".
- Trust the response's `sections_available` over any hardcoded list, and
  feature-detect optional artifacts (`mroi_periods`, `cohort_ledger`,
  post-#629 `*_mean` keys) — older fits simply lack them; there is no
  backfill.
