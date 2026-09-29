"""Bounded structured result grading, independent of dispatch and providers."""

import json
import re


def literal_fields(task, facts):
    """Retain the original exact-field metric separately from semantic acceptance."""
    return isinstance(facts, dict) and all(facts.get(k) == v for k, v in task.expected.items())


def semantic_facts(task, facts, supported_sections):
    """Bounded equivalences, not a general language judge or fuzzy numeric scorer.

    Display names require the returned canonical map. Boolean evidence states
    never coerce integers/strings. Unsupported explanations remain outside this
    structured-fact metric and require separate claim review.
    """
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
    if (task.family or task.id) == "result_diagnostics":
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
            "not saved",
            "both diagnostic sections were not saved",
            "the diagnostics are unavailable",
            "diagnostics are unavailable",
            "diagnostics were not saved",
        }
    aliases = {"Search Activity": "Search", "TV_activity": "TV"}
    if facts.get("channel") == aliases.get(task.channel) and "channel_map" in supported_sections:
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
    if not isinstance(facts, dict):
        return False
    allowed = set(task.expected)
    if (task.family or task.id) == "result_diagnostics":
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
    if (task.family or task.id) == "result_diagnostics" and isinstance(facts, dict):
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
