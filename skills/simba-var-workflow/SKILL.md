---
name: simba-var-workflow
description: Long-term (VAR) modeling workflow over Simba MCP — create a VAR model, poll its longer fit, link it to an MMM, and read the combined long-run rollup. Use when quantifying long-term/brand-equity effects beyond the MMM's short-term window.
---

# Simba VAR workflow (create → poll → link → rollup)

## 1. Create

`create_var_model` with `endogenous_vars` (the jointly-modeled series —
include the KPI and equity/brand metrics), optional `exogenous_vars`,
`lags`, `forecast_horizon`, and the long-run-effects settings
(`base_variable`, `equity_variables`, `lre_horizon`, `lre_ci`).
`var_priors` is strictly validated — unknown keys 400.

## 2. Poll

`get_model_status` as with MMMs, but expect VAR fits to run LONG — the
first fit on a worker includes heavy JIT compilation and can take well
over an hour; a retry after an apparent stall is normal platform behavior,
not failure. Only `failed` status is failure; use `get_model` for the
error message.

## 3. Link

`link_var_model(model_hash, var_model_hash)` attaches the VAR to a
completed MMM (same owner). One VAR can serve as the long-run layer for an
MMM; `unlink_var_model` detaches it. Deleting a failed VAR via
`delete_model` automatically unlinks any MMMs pointing at it.

## 4. Read the rollup

`get_model_results(mmm_hash, sections="long_run_rollup")` serves the
combined view: MMM short-term revenue joined with the VAR's long-run
elasticity bridge, per channel. Feature-detect: an MMM with no linked VAR
returns `{available: false, reason: "no_linked_var_model"}` — that is a
state, not an error. The MMM's other sections are unchanged by linking;
the rollup is the only joint artifact.

Channel naming still follows the MMM's activity-column rule; the VAR's own
config echo (`get_model` on the VAR hash) reports `endogenous_vars` /
`exogenous_vars` instead of channels.
