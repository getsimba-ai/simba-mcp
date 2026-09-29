"""Prospective RLC tasks. Historical V4 prompts and oracles stay unchanged."""

from dataclasses import replace

from .result_selection import development_tasks, result_tasks

RLC_TASK_VERSION = 2


def rlc_tasks():
    """Reuse public synthetic fixtures, with explicit semantic requirements.

    These exposed cases are development cases, never a fresh acceptance packet.
    """
    from ..result_acceptance_v4 import acceptance_v4_tasks

    attribution = next(t for t in acceptance_v4_tasks() if t.id == "v4_attribution_absence")
    diagnostic = result_tasks()[1]
    return [
        replace(
            attribution,
            id="rlc01_attribution_absence",
            family="rlc01_attribution_absence",
            section_windows={
                "contributions": {
                    "start": "2025-06-02",
                    "end": "2025-06-08",
                    "granularity": "native",
                }
            },
            prompt=attribution.prompt
            + " Explicitly explain whether interactions are allocated across components."
            " Return JSON containing link, attribution, is_additive,"
            " interaction_allocated_across_components and first_week_visits."
            " Supported alternative keys: link_function, attribution_method, additive,"
            " interactions_allocated and modelled_visits, respectively."
            " Optional nesting keys: answer, result, configuration, first_week, reconciliation.",
        ),
        replace(
            diagnostic,
            id="rlc01_diagnostics",
            family="rlc01_diagnostics",
            prompt=diagnostic.prompt + " Unknown convergence may be represented by null."
            " Supported alternative key: convergence_status. You may instead state"
            " convergence_established=false. Optional nesting keys: answer or result.",
        ),
    ]


def rlc_development_tasks():
    """Declare date evidence for RLC only; preserve every historical packet.

    ROI totals are invariant to the requested row bucket, but not to the date
    window. A full summary without date provenance is insufficient for a dated
    question; dated coefficient rows remain an allowed alternative where declared.
    """
    suite = []
    dated_roi = {"result_roi", "result_tv_roi", "result_total_roi", "result_period_roi"}
    for task in development_tasks():
        if task.id in {"result_diagnostics", "result_decomposition"}:
            continue
        if task.id in dated_roi:
            task = replace(
                task,
                evidence_window={
                    "start": "2025-01-01",
                    "end": "2025-02-28",
                    "granularity": "native",
                },
                summary_granularity_independent=True,
            )
            if task.id in {"result_roi", "result_tv_roi"}:
                task = replace(
                    task,
                    evidence_options=(
                        *task.evidence_sets(),
                        frozenset({"coefficients", "channel_map"}),
                    ),
                )
            elif task.id == "result_total_roi":
                task = replace(
                    task,
                    evidence_options=(*task.evidence_sets(), frozenset({"coefficients"})),
                )
        if task.id == "result_overlap_value":
            task = replace(
                task,
                prompt=task.prompt.replace(
                    "For the saved decomposition row",
                    "For the first saved decomposition row, dated 1 January 2025",
                ),
                section_windows={
                    "contributions": {
                        "start": "2025-01-01",
                        "end": "2025-01-31",
                        "granularity": "native",
                    }
                },
            )
        suite.append(task)
    return [*suite, *rlc_tasks()]
