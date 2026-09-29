"""Labelled structured-answer calibration, separate from provider execution.

Labels are engineering expectations for review, not human-approved ground truth.
Original provider evidence is never overwritten or silently rescored.
"""

from dataclasses import asdict

from .result_grading import claims_in_scope, fact_verdict, semantic_facts
from .result_selection import result_tasks

GRADER_VERSION = 8


def calibration_cases():
    roi, diagnostic, marginal, decomposition, old = result_tasks()
    cases = [
        (
            "valid_explanation_for_review",
            diagnostic,
            {
                "convergence": False,
                "reason": "Both requested sections are absent from the response. "
                "Missing diagnostics do not prove convergence or failure.",
            },
            set(),
            False,
            True,
        ),
        ("correct_roi", roi, roi.expected, {"channel_map"}, True, True),
        (
            "mapped_display_name",
            roi,
            {**roi.expected, "channel": "Search"},
            {"channel_map"},
            True,
            True,
        ),
        ("unverified_display_name", roi, {**roi.expected, "channel": "Search"}, set(), False, True),
        (
            "inline_marginal_identity",
            marginal,
            {**marginal.expected, "channel": "Search"},
            {"verified_channel_identity"},
            True,
            True,
        ),
        ("average_ratios", roi, {**roi.expected, "roi": 3.0}, set(), False, True),
        ("boolean_ratio", roi, {**roi.expected, "roi": True}, set(), False, True),
        ("invented_claim", roi, {**roi.expected, "causally_valid": True}, set(), True, False),
        ("wrong_interval", marginal, {**marginal.expected, "upper": 2.2}, set(), False, True),
        (
            "wrong_interval_probability",
            marginal,
            {**marginal.expected, "hdi_prob": 0.95},
            set(),
            False,
            True,
        ),
        (
            "integer_not_boolean",
            decomposition,
            {**decomposition.expected, "overlap_is_channel": 0},
            set(),
            False,
            True,
        ),
        ("nested_unavailable", old, {"mroi_periods": old.expected}, set(), True, True),
        (
            "contradictory_availability",
            old,
            {"available": True, "mroi_periods": old.expected},
            set(),
            False,
            True,
        ),
        (
            "nested_extra_claim",
            old,
            {"mroi_periods": {**old.expected, "safe_to_invest": True}},
            set(),
            True,
            False,
        ),
        ("unknown_diagnostic", diagnostic, diagnostic.expected, set(), True, True),
        (
            "boolean_unknown",
            diagnostic,
            {"convergence": False, "reason": "Both diagnostic sections were not returned."},
            set(),
            True,
            True,
        ),
        (
            "unknown_with_failure_claim",
            diagnostic,
            {"convergence": "unknown", "reason": "Diagnostics not returned but convergence failed"},
            set(),
            False,
            True,
        ),
        (
            "failed_not_unknown",
            diagnostic,
            {"convergence": "failed", "reason": "not_returned"},
            set(),
            False,
            True,
        ),
        (
            "pass_not_unknown",
            diagnostic,
            {"convergence": True, "reason": "not_returned"},
            set(),
            False,
            True,
        ),
        (
            "conflicting_unknown",
            diagnostic,
            {"convergence": "unknown", "convergence_established": True, "reason": "not_returned"},
            set(),
            False,
            True,
        ),
        ("missing_reason", diagnostic, {"convergence": False}, set(), False, True),
    ]
    return [
        {
            "id": name,
            "task": asdict(task),
            "facts": facts,
            "supported_sections": sorted(evidence),
            "expected_facts": correct,
            "expected_claims_in_scope": bounded,
        }
        for name, task, facts, evidence, correct, bounded in cases
    ]


def calibrate():
    tasks = {t.id: t for t in result_tasks()}
    rows = []
    for case in calibration_cases():
        task = tasks[case["task"]["id"]]
        actual = semantic_facts(task, case["facts"], set(case["supported_sections"]))
        bounded = claims_in_scope(task, case["facts"])
        verdict = fact_verdict(task, case["facts"], set(case["supported_sections"]))
        expected_verdict = (
            "review"
            if case["id"] in ("unknown_with_failure_claim", "valid_explanation_for_review")
            else "pass"
            if case["expected_facts"]
            else "fail"
        )
        case["task"]["required_sections"] = sorted(case["task"]["required_sections"])
        case["task"]["evidence_options"] = [sorted(s) for s in case["task"]["evidence_options"]]
        rows.append(
            {
                **case,
                "actual_facts": actual,
                "actual_claims_in_scope": bounded,
                "verdict": verdict,
                "expected_verdict": expected_verdict,
                "passed": actual == case["expected_facts"]
                and bounded == case["expected_claims_in_scope"]
                and verdict == expected_verdict,
            }
        )
    return {
        "grader_version": GRADER_VERSION,
        "passed": all(r["passed"] for r in rows),
        "label_review": "engineering_labels_pending_independent_review",
        "cases": rows,
    }
