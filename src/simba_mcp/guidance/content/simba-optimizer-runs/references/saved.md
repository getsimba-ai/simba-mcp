# Compare exact saved allocations

Marketer, reviewer and full/data_scientist can read `show_optimizer_allocation`,
`list_runs` and `get_optimizer_results`. Supply known model_hash and run_id directly.
If run ID is missing and identity matters, list existing runs before reading. Omitting
run_id selects the latest model-level state, which may belong to another run.

Compare saved runs using the exact model/run identity, currency, inputs and status.
Keep solver decision Revenue/ROI separate from fitted-convention OptimizedEvalRevenue/ROI
and HistoricalRevenue/ROI. ObjectiveMarginal is not posterior MroiAtOptimized.
The view returns unchanged JSON and text on non-visual clients. A read starts no
optimiser, scenario or fit, and grants no spending authority.

Missing/failed/pending evidence does not become a usable comparison. Inspect the exact
saved status and retain the reason; do not rerun automatically. Curation update_run
and set_run_pinned are marketer/full writes and require explicit user intent.
Use section=saved-examples for a two-run comparison with distinct decision/comparison values.
