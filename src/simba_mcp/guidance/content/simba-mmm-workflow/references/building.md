## 1. Upload

1. Call `get_data_schema` first and validate the CSV against it; especially
   `x-simba-constraints.min_rows` and the media naming rule
   `{channel}_activity` / `{channel}_spend`. Inactive periods are `0`, never
   blank/NA. CSV only, 10 MB max.
2. `upload_data` with `csv_path` when the server runs locally (stdio) ,
   large files must not transit the conversation. On hosted servers pass
   `csv_content`. The response's `warnings` field is authoritative on row
   sufficiency.
3. `list_uploads` / `get_upload` recover past uploads; `get_upload`'s
   `columns` ([{name, dtype}]) is enough to build `create_model` arguments
   without re-reading the CSV.
4. To report actual data (any window, any column, by brand/channel/market)
   use `get_data_report`, not model results. Declare column roles; at
   upload (`upload_data(roles=...)`) or per call; for the KPI, hierarchy and
   any outcome, media or control column; only `date`, `{channel}_spend` and
   `{channel}_activity` are recognised without a declaration, and roles are
   never guessed.

## 2. Create

- Minimal call: `uploaded_file_id`, `date_column`, `kpi_column`,
  `hierarchy_column` (exactly 1 unique value), `channels`
  ([{name, activity_column, spend_column}]).
- Decide **at create time** if profit analysis is ever wanted: pass
  `operating_margin` (scalar fraction) or `operating_margin_column`. These
  are TOP-LEVEL parameters; a margin placed inside a config dict is
  silently ignored and the model fits marginless. Without a stored margin,
  `financials` never appears and every profit optimisation must re-supply
  `forward_margin`.
- Multiplicative form: `link="log"`; attribution conventions other than
  `removal_lift` require it. Priors: read the bundled prior reference before overriding anything.
- The response is a `model_hash` immediately; fitting is async.
- **Calibrate with recorded incrementality tests.** `list_incrementality_tests`
  shows the project's geo, owned-media and platform-lift results (Simba records
  tests analysed elsewhere; it fits nothing). Check a test against a saved model
  on the same data with `get_incrementality_test(test_id, model_hash=...)`: its
  `calibration` is the likelihood row, or a refusal reason (e.g.
  `channel_not_in_model`: pass `channel`; `kpi_mismatch`: pass `confirm_kpi`
  only if the outcome truly is the model's KPI). Then
  `create_model(..., calibration={"tests": [{"test_id": ...}]})`. A refused test
  fails the call with `calibration_refused` and a reason per test; nothing is
  created. New results: `create_incrementality_test`, or
  `import_incrementality_tests` (dry run first, then `dry_run=false`).

## 3. Poll

- `get_model_status` until `complete` or `failed`. Fits take minutes to
  tens of minutes; poll with backoff, don't spin.
- On `failed`: `get_model` returns the error message plus the full config
  echo (it works for every status). Fix the config and re-create;
  `delete_model` cleans up the failed entry (failed-only; destructive).
- Models start unsaved (invisible to default `list_models`); `save_model`
  files them into a project; `rename_model` names without saving.


If the backend returns `fit_liveness`, use its heartbeat age and configured
threshold to describe liveness separately from fit progress. The threshold
countdown is not completion ETA or an exact termination time. An absent field
or `available: false` means unknown liveness, not a healthy or stalled fit.
An exceeded threshold does not itself change model status. Poll with backoff;
do not automatically restart or duplicate a fit based on this metadata.
