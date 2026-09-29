"""Bounded structured result grading, independent of dispatch and providers."""

import json
import re

# This bounded vocabulary is prospective and task-specific. It is not an
# entailment model: novel prose and extra claims always need independent review.
_RLC_ALIASES = {
    "rlc01_attribution_absence": {
        "link_function": "link",
        "attribution_method": "attribution",
        "additive": "is_additive",
        "interactions_allocated": "interaction_allocated_across_components",
        "modelled_visits": "first_week_visits",
    },
    "rlc01_diagnostics": {"convergence_status": "convergence"},
}
_RLC_CONTAINERS = {"answer", "result", "configuration", "first_week", "reconciliation"}


def _rlc_normalise(task, facts):
    """Collect only declared leaves, retaining duplicate contradictions.

    Unknown containers and leaves are not stripped: they make scope fail.
    Equality never treats booleans as numbers, including duplicate values.
    """
    family = task.family or task.id
    aliases = _RLC_ALIASES.get(family)
    if aliases is None:
        return facts, True
    if not isinstance(facts, dict):
        return facts, False
    collected = {}
    scoped = True
    conflict = False

    def visit(obj):
        nonlocal scoped, conflict
        for key, value in obj.items():
            if key in _RLC_CONTAINERS and isinstance(value, dict):
                visit(value)
                continue
            key = aliases.get(key, key)
            if key not in task.expected and not (
                family == "rlc01_diagnostics" and key == "convergence_established"
            ):
                scoped = False
                continue
            if family == "rlc01_diagnostics" and key == "convergence" and value is None:
                value = "unknown"
            if key == "attribution" and isinstance(value, str):
                value = {
                    "Aumann-Shapley": "aumann_shapley",
                    "Aumann Shapley": "aumann_shapley",
                }.get(value, value)
            if key in collected and (
                collected[key] != value
                or isinstance(collected[key], bool) != isinstance(value, bool)
            ):
                conflict = True
            collected[key] = value

    visit(facts)
    return (None if conflict else collected), scoped


def _missing_diagnostic_task(task):
    """Apply absence equivalences only to the exact absence question contract."""
    return (task.family or task.id) in (
        "result_diagnostics",
        "rlc01_diagnostics",
    ) and task.expected == {
        "convergence": "unknown",
        "reason": "not_returned",
    }


def literal_fields(task, facts):
    """Retain the original exact-field metric separately from semantic acceptance."""
    return isinstance(facts, dict) and all(facts.get(k) == v for k, v in task.expected.items())


def semantic_facts(task, facts, supported_sections):
    """Bounded equivalences, not a general language judge or fuzzy numeric scorer.

    Display names require the returned canonical map. Boolean evidence states
    never coerce integers/strings. Unsupported explanations remain outside this
    structured-fact metric and require separate claim review.
    """
    facts, _ = _rlc_normalise(task, facts)
    if not isinstance(facts, dict):
        return False
    facts = dict(facts)
    if (task.family or task.id) == "result_old_artifact" and "mroi_periods" in facts:
        nested = facts["mroi_periods"]
        if not isinstance(nested, dict):
            return False
        if any(k in facts and facts[k] != nested.get(k) for k in ("available", "reason")):
            return False
        facts = nested
    if _missing_diagnostic_task(task):
        state = facts.get("convergence")
        established = facts.get("convergence_established")
        if "convergence" in facts and not (
            state is False
            or (isinstance(state, str) and state in ("unknown", "unavailable", "not_established"))
        ):
            return False
        if "convergence_established" in facts and established is not False:
            return False
        if state is None and established is not False:
            return False
        reason = facts.get("reason")
        if not isinstance(reason, str):
            return False
        # Missing saved evidence, not failed convergence, is the fact at issue.
        normal = reason.lower().replace("_", " ")
        return normal.strip().rstrip(".") in {
            "not returned",
            "both diagnostic sections were not returned",
            "the diagnostics are unavailable",
            "diagnostics are unavailable",
            "diagnostics were not returned",
        }
    aliases = {"Search Activity": "Search", "TV_activity": "TV"}
    if (
        facts.get("channel") == aliases.get(task.channel)
        and {"channel_map", "verified_channel_identity"} & supported_sections
    ):
        facts["channel"] = task.channel
    for key, expected in task.expected.items():
        actual = facts.get(key)
        if isinstance(expected, bool):
            if actual is not expected:
                return False
        elif isinstance(expected, (int, float)):
            if type(actual) not in (int, float) or actual != expected:
                return False
        elif actual != expected:
            return False
    return True


def claims_in_scope(task, facts):
    """Unexpected structured claims require review, rather than silently passing.

    This is a schema boundary, not natural-language entailment. Free prose outside
    the parsed answer is reported separately by the host runner.
    """
    facts, scoped = _rlc_normalise(task, facts)
    if not isinstance(facts, dict) or not scoped:
        return False
    allowed = set(task.expected)
    if _missing_diagnostic_task(task):
        allowed.add("convergence_established")
    if (task.family or task.id) == "result_old_artifact" and "mroi_periods" in facts:
        nested = facts["mroi_periods"]
        if not isinstance(nested, dict) or not set(nested) <= allowed:
            return False
        allowed.add("mroi_periods")
    return set(facts) <= allowed


def fact_verdict(task, facts, supported_sections):
    """Separate definite structured mismatches from explanations needing review.

    A correct unknown-convergence state with an unfamiliar reason is not a
    proven false claim. Its explanation needs independent semantic review.
    """
    if semantic_facts(task, facts, supported_sections):
        return "pass"
    facts, _ = _rlc_normalise(task, facts)
    if _missing_diagnostic_task(task) and isinstance(facts, dict):
        state = facts.get("convergence")
        established = facts.get("convergence_established")
        state_valid = (
            state is False
            or (isinstance(state, str) and state in ("unknown", "unavailable", "not_established"))
            or ("convergence" not in facts and established is False)
        )
        if (
            state_valid
            and ("convergence_established" not in facts or established is False)
            and isinstance(facts.get("reason"), str)
            and facts["reason"].strip()
        ):
            return "review"
    return "fail"


def structured_answer_only(text):
    """Code fencing is formatting; prose outside the answer still needs review."""
    text = text.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return isinstance(json.loads(text), (dict, list))
    except ValueError:
        return False
