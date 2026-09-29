"""Prospective RLC tasks. Historical V4 prompts and oracles stay unchanged."""

from dataclasses import replace

from .result_selection import result_tasks


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
