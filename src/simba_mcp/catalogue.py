"""Optional model-facing wording; handlers, schemas and effects keep their existing owners."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Description:
    text: str
    domain: str
    topic: str


# Deliberately curate the largest descriptions first. All other tools retain their
# full descriptions; no automatic truncation or second schema/effect registry.
COMPACT = {
    "create_model": Description(
        """Create and queue a Bayesian MMM fit; returns model_hash immediately. This writes
state and can consume fitting resources. Poll get_model_status with backoff; inspect
get_model on failure. Reconcile an uncertain submission before repeating a write.

Required: uploaded_file_id, date_column, kpi_column, hierarchy_column (one unique
value), channels=[{name, activity_column, spend_column}]. Use exact dataset columns.
For new data validate get_data_schema first. Supply requested settings explicitly;
never drop unsupported settings to make a fit succeed. Unspecified priors use smart
defaults based on configured assumptions, not independent scientific evidence.

sampler uses n_samples (posterior samples), tune (tuning iterations) and chains;
draws is not a supported key. Media priors are a list of overrides, for example
[{"channel": "Search", "mean": 0.2, "sd": 0.1}] for the coefficient prior.
Media priors identify channels[].name via channel. Supply only overrides. Unknown
prior/sampler keys reject. Carryover types: geometric, delayed, dual_geometric.
half_life_lower/upper are periods; theta_* only applies to delayed, dual_weight_*
only to dual_geometric. Inspect accepted_not_used for inert parameters.
Choose one saturation anchor: half_saturation_mean/sd in activity units, legacy
alpha_sd/scalars, or half_marginal_mean/sd for generalized_log. For generalized_log,
half_marginal_* and effect_at_avg_* require sat_shape_mean in the same override.
effect_at_avg_mean is a fraction in (0, 0.95], sd > 0; do not combine with raw
mean/sd or half_saturation_*. Check get_model model_config.priors_resolved and
overridden_fields after creation. Read priors/conventions guidance before advanced
overrides; read mmm/tool-reference for the complete parameter contract.

link=log selects multiplicative modelling; non-removal_lift attribution requires
log. Overlap under removal_lift is a reconciliation term, not a channel. For profit,
operating_margin (fraction) or operating_margin_column belongs at the request root,
not inside config. multiplier_column converts KPI units to revenue.
control_columns selects exact controls; control_priors names control, not channel.
Explicit control overrides require advertised support, enforced by this tool; use
priors/conventions for transform units and family fields. Preserve requested settings.

calibration.tests references recorded incrementality test IDs. Refused calibration
creates nothing; inspect reasons and do not claim absent evidence is validated.
Saved training/prediction windows and diagnostics must support subsequent claims;
fit completion alone is not convergence, holdout validation or human acceptance.
Models begin unsaved; use save_model to file a completed model into a project.
Full guidance: get_workflow_guidance(topic=mmm, section=tool-reference).""",
        "models",
        "mmm",
    ),
    "get_model_results": Description(
        """Read selected results from a completed model. Request sections as a comma-separated
string; use channels, max_grid_points and max_response_bytes to bound output.
The byte cap is checked after backend download, not a transport download limit.
Existing-result questions need no mandatory capability/schema discovery. A missing
artifact is unavailable evidence, not zero or a passing diagnostic.

Use channel_summary for exact result keys. When relating a user-facing channel
name to a result or activity key, retrieve channel_map and use its explicit
mapping; do not infer identity from spelling. Request channel_map with the needed
result sections when possible. Result keys are exact, case-sensitive
ACTIVITY-COLUMN names, not channels[].name. Use these keys in optimiser/scenario
inputs. contributions is KPI units; coefficients is per-period revenue space;
channel_summary provides aggregated revenue/spend/ROI. Never equate largest
contribution with highest ROI. posterior and posterior_transforms use 94% HDIs
(hdi_3%/hdi_97%); actual_vs_model has its own 50%/95% bands. model_stats gives fit
diagnostics; r_hat covers all posterior variables, including transforms. Interpret
against the declared policy; missing diagnostics do not establish convergence.

start/end are inclusive ISO dates. granularity windows per-period sections and
recomputes channel_summary: ROI is summed revenue / summed spend, not averaged ROI.
Never sum mROI; read meta.aggregation. Contribution/coefficient dates are epoch
milliseconds. Overlap only occurs for log + removal_lift: it is reconciliation,
never a channel to rank, share or optimise. Its absence does not imply additive form.

sections_available is authoritative. response_curves/decay_curves/marginal_curves
describe fitted responses; mroi_summary is marginal ROI at current spend, with
optional means/conventions. mroi_periods and prediction_window are opt-in sections.
Serving prediction_window for a study-linked model appends an access-audit event;
it does not certify an untouched holdout. Channel/grid filters do not alter it.
financials is absent for marginless models; operating_margin_series is a date-keyed
dict. cohort_ledger and long_run_rollup require available saved artifacts. A missing
VAR link is not a zero long-term effect; check rollup coverage and channel mapping.
model_config reports effective inputs and priors_resolved, including accepted_not_used.
On refusal follow the structured next action, narrow deliberately rather than
silently losing evidence. Full section/filter/export semantics:
get_workflow_guidance(topic=results, section=tool-reference).""",
        "results",
        "results",
    ),
    "run_optimizer": Description(
        """Queue budget optimisation on a completed model and return run_id. This writes
state; confirm the objective and constraints first. Poll get_optimizer_results
with that run_id and backoff, not the mutable model-level latest result. Reconcile
uncertain writes through run history before resubmitting.

Use exact ACTIVITY-COLUMN channel keys from channel_summary/get_scenario_template,
not display names. total_budget is currency; bounds are percentages (0-100) of
that total, not money. bounds, laydown_weights and period_cpm must name the same
channels. bounds maps each channel to {"lower": 20, "upper": 100}, not an array.
Each laydown/CPM value is an array of length num_periods; CPMs are positive.
gamma controls uncertainty aversion: zero maximises expected return.
objective=revenue is default; profit needs a stored operating margin or
forward_margin (scalar fraction). period_multiplier is a num_periods
array converting KPI to revenue. Preserve requested objective/settings on refusal.

optimizer_engine=slsqp is default; marginal supports water-filling with SLSQP
fallback. sigma_penalty defaults to std. group_bounds uses disjoint feasible
channel sets with percentage lower/upper, forces slsqp, and a binding group's
channels need not share the unconstrained global marginal.
include_historical_effect and enable_warm_start default true.

Revenue/ROI are solver decision values; OptimizedEvalRevenue/ROI and
HistoricalRevenue/ROI are fitted-convention comparisons. For profit the decision
values use the profit basis. ObjectiveMarginal differs from posterior
MroiAtOptimized. Report the basis and constraints; output is not approval to spend.
Full parameter and interpretation contract:
get_workflow_guidance(topic=optimiser, section=tool-reference).""",
        "scenarios",
        "optimiser",
    ),
}


def description_for(handler: Callable, mode: str) -> str | None:
    if mode not in ("legacy", "compact"):
        raise ValueError("Tool description mode must be legacy or compact")
    entry = COMPACT.get(handler.__name__)
    return entry.text if mode == "compact" and entry else None
