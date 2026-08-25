---
name: simba-optimizer-runs
description: Run Simba budget optimizations correctly over MCP — payload conventions (percent bounds, laydown/CPM arrays), revenue vs profit objectives, polling by run_id, interpreting decision vs comparison columns, and curating run history. Use when optimizing budgets or reading optimizer results through the Simba MCP tools.
---

# Simba optimizer runs

## Payload rules (the four that reject or mislead)

1. Channel keys = ACTIVITY-COLUMN names, case- and space-sensitive. Get
   them from `channel_summary` or `get_scenario_template`
   (`avg_cpu_by_channel` doubles as baseline CPM).
2. `bounds` are PERCENTAGES of `total_budget` (0–100), not currency.
3. `laydown_weights` and `period_cpm` are ARRAYS of length `num_periods`
   ({"TV": [10, 10, 10, 10]}, never {"TV": 10}); CPMs strictly positive;
   the same channel keys must appear in `bounds`, `laydown_weights`, AND
   `period_cpm`.
4. `gamma` is uncertainty aversion (objective = mean − gamma·spread):
   0 = maximize expected return; higher = more conservative. Typical
   dashboard range 0–0.1.

## Objectives and margin

- `objective="profit"` needs a margin: the model's stored operating margin
  is used automatically; otherwise pass `forward_margin` or the API errors.
  Result Revenue/ROI columns are then on the profit basis.
- `group_bounds` (joint % constraints over channel sets) forces the slsqp
  engine; a BINDING group's members legitimately sit off the global
  marginal.

## Poll and read

- `run_optimizer` returns 202 + a `run_id` ("opt_..."). Poll
  `get_optimizer_results(model_hash, run_id=...)` — the model-level form
  reflects only the LATEST run and a newer run overwrites it.
- Column conventions must not be mixed in one summary:
  - `Revenue`/`ROI` = the solver's decision math (removal-lift
    counterfactual).
  - `OptimizedEvalRevenue/ROI`, `HistoricalRevenue/ROI` = fitted-convention
    comparison columns (match the Contributions panel).
  - `ObjectiveMarginal` (solver's equalized marginal) ≠ `MroiAtOptimized`
    (posterior mROI at the optimized spend, with 94% HDI) — they can differ
    by several times; quote the one matching the question.

## Run history and curation

- `list_runs(artifact="optimizer"|"scenario", ...)`: pinned-first then
  newest-first. `count` is the PAGE length, not the total — page until a
  short page. The objective is NOT in summaries: fetch the run's `inputs`
  (profit runs carry `objective: "profit"`; revenue runs omit the key).
- `update_run` renames/annotates (sets `auto_named` false permanently);
  `set_run_pinned` pins declaratively and idempotently. Scenario runs work
  the same via `get_scenario_results(run_id=...)`.
