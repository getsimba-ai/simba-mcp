"""Bounded structured result grading, independent of dispatch and providers."""

import re

from ..json_data import load_json

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


def _old_artifact_task(task, grader_version):
    if grader_version >= 20:
        return task.id == "result_old_artifact" and task.expected == {
            "available": False,
            "reason": "fitted_before_mroi_periods",
        }
    return (task.family or task.id) == "result_old_artifact"


def _artifact_conflicts(facts, nested, grader_version):
    return any(
        key in facts
        and (
            facts[key] != nested.get(key)
            or (
                grader_version >= 20
                and type(nested.get(key)) is bool
                and facts[key] is not nested[key]
            )
        )
        for key in ("available", "reason")
    )


def _fact_matches(actual, expected, *, allow_extra=False):
    """Numeric JSON parity never makes a Boolean or nested claim equivalent."""
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and (set(expected) <= set(actual) if allow_extra else set(actual) == set(expected))
            and all(
                _fact_matches(actual[key], value, allow_extra=allow_extra)
                for key, value in expected.items()
            )
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(
                _fact_matches(a, e, allow_extra=allow_extra)
                for a, e in zip(actual, expected, strict=True)
            )
        )
    if isinstance(expected, bool):
        return actual is expected
    if type(expected) in (int, float):
        return type(actual) in (int, float) and actual == expected
    return type(actual) is type(expected) and actual == expected


def _merge_compatible_claims(left, right):
    """Merge compatible metadata, never discard disagreeing duplicate claims."""
    if isinstance(left, dict) and isinstance(right, dict):
        merged = dict(left)
        for key, value in right.items():
            if key in merged:
                value, compatible = _merge_compatible_claims(merged[key], value)
                if not compatible:
                    return None, False
            merged[key] = value
        return merged, True
    return left, _fact_matches(left, right)


def _workflow_normalise_v21(task, facts):
    """Declared workflow grouping only; extras and contradictions remain visible."""
    if not isinstance(facts, dict):
        return facts, True
    containers = {
        "role_saved_allocation": {"deltas"},
        "role_campaign_facts": {"campaign_incrementality"},
        "role_campaign_budget": {"marginal_evidence", "allocation_recommendation", "allocation"},
    }.get(task.id, set())
    result = {key: value for key, value in facts.items() if key not in containers}
    for container in containers & facts.keys():
        grouped = facts[container]
        if (
            container in ("allocation", "campaign_incrementality")
            and isinstance(grouped, list)
            and len(grouped) == 1
        ):
            grouped = grouped[0]
        if not isinstance(grouped, dict):
            return facts, False
        extras = {}
        for key, value in grouped.items():
            if key not in task.expected:
                extras[key] = value
                continue
            if key in result:
                value, compatible = _merge_compatible_claims(result[key], value)
                if not compatible:
                    return facts, False
            result[key] = value
        if extras:
            result[container] = extras
    if task.id == "role_experiment_unsupported":
        # Canonical transport message and next action, not arbitrary prose matching.
        if result.get("reason") in (
            "Backend request failed with unsupported_operation (HTTP 405)",
            "unsupported_operation (HTTP 405)",
            "The endpoint is unsupported (HTTP 405).",
        ):
            result["reason"] = "unsupported_operation"
        if (
            result.get("next_action")
            == "handoff: Check whether this backend supports the requested operation."
        ):
            result["next_action"] = "handoff"
    return result, True


def semantic_facts(task, facts, supported_sections, *, grader_version=17):
    """Bounded equivalences, not a general language judge or fuzzy numeric scorer.

    Display names require the returned canonical map. Boolean evidence states
    never coerce integers/strings. Unsupported explanations remain outside this
    structured-fact metric and require separate claim review.
    """
    if type(grader_version) is not int or grader_version not in (17, 18, 19, 20, 21):
        raise ValueError("Unsupported result grader version")
    if grader_version >= 21:
        facts, scoped = _workflow_normalise_v21(task, facts)
        if not scoped:
            return False
    facts, _ = _rlc_normalise(task, facts)
    if not isinstance(facts, dict):
        return False
    facts = dict(facts)
    if _old_artifact_task(task, grader_version) and "mroi_periods" in facts:
        nested = facts["mroi_periods"]
        if not isinstance(nested, dict):
            return False
        if _artifact_conflicts(facts, nested, grader_version):
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
    if grader_version >= 18 and task.fixture is not None:
        # Generic identities come only from the explicit prospective contract.
        # Historical tasks without a fixture retain their fixed aliases above.
        mapping = task.fixture.get("results", {}).get("channel_map", [])
        candidates = [
            row
            for row in mapping
            if isinstance(row, dict) and row.get("activity_column") == task.channel
        ]
        # A single canonical identity is required. Evidence below must already
        # establish this mapping, not merely contain a similarly spelled key.
        aliases = {}
        if len(candidates) == 1 and isinstance(candidates[0].get("channel"), str):
            display = candidates[0]["channel"]
            if (
                display
                and sum(isinstance(row, dict) and row.get("channel") == display for row in mapping)
                == 1
            ):
                aliases[task.channel] = display
    if (
        (grader_version == 17 or isinstance(aliases.get(task.channel), str))
        and facts.get("channel") == aliases.get(task.channel)
        and {"channel_map", "verified_channel_identity"} & supported_sections
    ):
        facts["channel"] = task.channel
    for key, expected in task.expected.items():
        if grader_version >= 21 and key not in facts:
            return False
        actual = facts.get(key)
        if grader_version >= 20:
            if not _fact_matches(actual, expected, allow_extra=grader_version >= 21):
                return False
        elif isinstance(expected, bool):
            if actual is not expected:
                return False
        elif isinstance(expected, (int, float)):
            if type(actual) not in (int, float) or actual != expected:
                return False
        elif actual != expected:
            return False
    return True


def claims_in_scope(task, facts, *, grader_version=17):
    """Unexpected structured claims require review, rather than silently passing.

    This is a schema boundary, not natural-language entailment. Free prose outside
    the parsed answer is reported separately by the host runner.
    """
    if grader_version >= 21:
        facts, scoped = _workflow_normalise_v21(task, facts)
        if not scoped:
            return False
    facts, scoped = _rlc_normalise(task, facts)
    if not isinstance(facts, dict) or not scoped:
        return False
    allowed = set(task.expected)
    if _missing_diagnostic_task(task):
        allowed.add("convergence_established")
    if _old_artifact_task(task, grader_version) and "mroi_periods" in facts:
        nested = facts["mroi_periods"]
        if (
            not isinstance(nested, dict)
            or not set(nested) <= allowed
            or (grader_version >= 20 and _artifact_conflicts(facts, nested, grader_version))
        ):
            return False
        allowed.add("mroi_periods")
    return set(facts) <= allowed and (
        grader_version < 21
        or all(
            _fact_matches(facts[key], expected)
            for key, expected in task.expected.items()
            if key in facts and isinstance(expected, (dict, list))
        )
    )


def fact_verdict(task, facts, supported_sections, *, grader_version=17):
    """Separate definite structured mismatches from explanations needing review.

    A correct unknown-convergence state with an unfamiliar reason is not a
    proven false claim. Its explanation needs independent semantic review.
    """
    if semantic_facts(task, facts, supported_sections, grader_version=grader_version):
        return "pass"
    if grader_version >= 21:
        facts, _ = _workflow_normalise_v21(task, facts)
    if (
        grader_version >= 21
        and task.id == "role_experiment_unsupported"
        and isinstance(facts, dict)
        and facts.get("available") is False
        and facts.get("next_action") == "handoff"
        and isinstance(facts.get("reason"), str)
        and facts["reason"].strip()
    ):
        return "review"
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
        return isinstance(load_json(text), (dict, list))
    except ValueError:
        return False
