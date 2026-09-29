"""Labelled structured-answer calibration, separate from provider execution.

Labels are engineering expectations for review, not human-approved ground truth.
Original provider evidence is never overwritten or silently rescored.
"""

from dataclasses import asdict

from .result_grading import claims_in_scope, semantic_facts
from .result_selection import result_tasks

GRADER_VERSION = 4


def calibration_cases():
    roi, diagnostic, marginal, decomposition, old = result_tasks()
    cases = [
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
            {"convergence": False, "reason": "Both diagnostic sections were not saved."},
            set(),
            True,
            True,
        ),
        (
            "unknown_with_failure_claim",
            diagnostic,
            {"convergence": "unknown", "reason": "Diagnostics not saved but convergence failed"},
            set(),
            False,
            True,
        ),
        (
            "failed_not_unknown",
            diagnostic,
            {"convergence": "failed", "reason": "not_saved"},
            set(),
            False,
            True,
        ),
        (
            "pass_not_unknown",
            diagnostic,
            {"convergence": True, "reason": "not_saved"},
            set(),
            False,
            True,
        ),
        (
            "conflicting_unknown",
            diagnostic,
            {"convergence": "unknown", "convergence_established": True, "reason": "not_saved"},
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
        case["task"]["required_sections"] = sorted(case["task"]["required_sections"])
        rows.append(
            {
                **case,
                "actual_facts": actual,
                "actual_claims_in_scope": bounded,
                "passed": actual == case["expected_facts"]
                and bounded == case["expected_claims_in_scope"],
            }
        )
    return {
        "grader_version": GRADER_VERSION,
        "passed": all(r["passed"] for r in rows),
        "label_review": "engineering_labels_pending_independent_review",
        "cases": rows,
    }
