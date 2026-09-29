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
            " Equivalent field names and nested objects are accepted.",
        ),
        replace(
            diagnostic,
            id="rlc01_diagnostics",
            family="rlc01_diagnostics",
            prompt=diagnostic.prompt + " Unknown convergence may be represented by null."
            " Equivalent field names and nested objects are accepted.",
        ),
    ]
