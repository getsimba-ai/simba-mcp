"""Labelled structured-answer calibration, separate from provider execution.

Labels are engineering expectations for review, not human-approved ground truth.
Original provider evidence is never overwritten or silently rescored.
"""

from dataclasses import asdict, replace

from .result_grading import claims_in_scope, fact_verdict, semantic_facts
from .result_rlc_tasks import rlc_tasks
from .result_selection import ResultTask, result_tasks

GRADER_VERSION = 17


def calibration_cases(*, grader_version=17):
    if type(grader_version) is not int or grader_version not in (17, 18, 19):
        raise ValueError("Unsupported result grader version")
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
    attribution, unknown = rlc_tasks()
    expected = attribution.expected
    cases.extend(
        [
            (
                "rlc_established_unknown",
                unknown,
                {"convergence_established": False, "reason": "not_returned"},
                set(),
                True,
                True,
            ),
            (
                "rlc_established_contradiction",
                unknown,
                {
                    "convergence": "unknown",
                    "convergence_established": True,
                    "reason": "not_returned",
                },
                set(),
                False,
                True,
            ),
            ("rlc_exact", attribution, expected, set(), True, True),
            ("rlc_nested", attribution, {"answer": expected}, set(), True, True),
            (
                "rlc_aliases",
                attribution,
                {
                    "configuration": {
                        "link_function": "log",
                        "attribution_method": "Aumann-Shapley",
                        "additive": False,
                        "interactions_allocated": True,
                    },
                    "first_week": {"modelled_visits": 55},
                },
                set(),
                True,
                True,
            ),
            (
                "rlc_paraphrase",
                attribution,
                {**expected, "attribution": "Aumann Shapley"},
                set(),
                True,
                True,
            ),
            (
                "rlc_wrong_total",
                attribution,
                {**expected, "first_week_visits": 56},
                set(),
                False,
                True,
            ),
            (
                "rlc_missing_allocation",
                attribution,
                {
                    k: v
                    for k, v in expected.items()
                    if k != "interaction_allocated_across_components"
                },
                set(),
                False,
                True,
            ),
            (
                "rlc_false_allocation",
                attribution,
                {**expected, "interaction_allocated_across_components": False},
                set(),
                False,
                True,
            ),
            (
                "rlc_absence_proves_additive",
                attribution,
                {**expected, "is_additive": True},
                set(),
                False,
                True,
            ),
            (
                "rlc_contradictory_alias",
                attribution,
                {**expected, "additive": True},
                set(),
                False,
                False,
            ),
            (
                "rlc_contradictory_nested",
                attribution,
                {**expected, "first_week": {"modelled_visits": 56}},
                set(),
                False,
                False,
            ),
            (
                "rlc_duplicate_equivalent",
                attribution,
                {**expected, "first_week": {"modelled_visits": 55.0}},
                set(),
                True,
                True,
            ),
            (
                "rlc_boolean_number",
                attribution,
                {**expected, "first_week_visits": True},
                set(),
                False,
                True,
            ),
            (
                "rlc_integer_boolean",
                attribution,
                {**expected, "is_additive": 0},
                set(),
                False,
                True,
            ),
            (
                "rlc_unknown_explanation",
                attribution,
                {**expected, "explanation": "This proves causal identification"},
                set(),
                True,
                False,
            ),
            (
                "rlc_hidden_extra",
                attribution,
                {"answer": {**expected, "causal": True}},
                set(),
                True,
                False,
            ),
            (
                "rlc_null_is_unknown",
                unknown,
                {"convergence": None, "reason": "not_returned"},
                set(),
                True,
                True,
            ),
            (
                "rlc_nested_unknown",
                unknown,
                {"result": {"convergence_status": None, "reason": "not_returned"}},
                set(),
                True,
                True,
            ),
            ("rlc_omitted_not_unknown", unknown, {"reason": "not_returned"}, set(), False, True),
            (
                "rlc_error_not_unknown",
                unknown,
                {"convergence": "request_failed", "reason": "not_returned"},
                set(),
                False,
                True,
            ),
            (
                "rlc_null_not_number",
                attribution,
                {**expected, "first_week_visits": None},
                set(),
                False,
                True,
            ),
            (
                "rlc_refusal_incomplete",
                attribution,
                {"error": "Cannot answer"},
                set(),
                False,
                False,
            ),
            (
                "rlc_false_method",
                attribution,
                {**expected, "attribution": "removal_lift"},
                set(),
                False,
                True,
            ),
        ]
    )
    if grader_version >= 18:
        cases.extend(canonical_identity_cases())
    return [
        {
            "id": name,
            "task": {k: v for k, v in asdict(task).items() if k != "period_evidence_granularity"},
            "facts": facts,
            "supported_sections": sorted(evidence),
            "expected_facts": correct,
            "expected_claims_in_scope": bounded,
        }
        for name, task, facts, evidence, correct, bounded in cases
    ]


def canonical_identity_cases():
    """Prospective labels only; historical version 17 rows remain unchanged."""
    roi = result_tasks()[0]
    mapping = {
        "channel": "Paid Discovery",
        "activity_column": "Discovery_units",
        "spend_column": "Discovery_cost",
    }
    task = replace(
        roi,
        id="canonical_identity_calibration",
        channel="Discovery_units",
        expected={**roi.expected, "channel": "Discovery_units"},
        fixture={"model_hash": "synthetic-calibration", "results": {"channel_map": [mapping]}},
    )
    answer = {**task.expected, "channel": "Paid Discovery"}
    ambiguous = replace(
        task,
        fixture={
            "model_hash": "synthetic-calibration",
            "results": {"channel_map": [mapping, {**mapping, "activity_column": "Other_units"}]},
        },
    )
    wrong = replace(
        task,
        fixture={
            "model_hash": "synthetic-calibration",
            "results": {"channel_map": [{**mapping, "channel": "Different channel"}]},
        },
    )
    return [
        ("generic_mapped_display", task, answer, {"channel_map"}, True, True),
        ("generic_inline_identity", task, answer, {"verified_channel_identity"}, True, True),
        ("generic_activity_key", task, task.expected, {"channel_map"}, True, True),
        ("generic_missing_mapping", task, answer, {"channel_summary"}, False, True),
        ("generic_wrong_mapping", wrong, answer, {"channel_map"}, False, True),
        ("generic_ambiguous_mapping", ambiguous, answer, {"channel_map"}, False, True),
        (
            "generic_spelling_guess",
            task,
            {**answer, "channel": "paid discovery"},
            {"channel_map"},
            False,
            True,
        ),
        ("generic_wrong_roi", task, {**answer, "roi": 9}, {"channel_map"}, False, True),
    ]


def calibrate(*, grader_version=17):
    rows = []
    for case in calibration_cases(grader_version=grader_version):
        task = ResultTask(**case["task"])
        actual = semantic_facts(
            task, case["facts"], set(case["supported_sections"]), grader_version=grader_version
        )
        bounded = claims_in_scope(task, case["facts"])
        verdict = fact_verdict(
            task, case["facts"], set(case["supported_sections"]), grader_version=grader_version
        )
        expected_verdict = (
            "review"
            if case["id"] in ("unknown_with_failure_claim", "valid_explanation_for_review")
            else "pass"
            if case["expected_facts"]
            else "fail"
        )
        case["task"]["required_sections"] = sorted(case["task"]["required_sections"])
        case["task"]["evidence_options"] = [sorted(s) for s in case["task"]["evidence_options"]]
        case["task"]["forbidden_result_sections"] = sorted(
            case["task"]["forbidden_result_sections"]
        )
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
    period_rows = []
    if grader_version >= 19:
        from .result_period_calibration import calibrate_periods

        period_rows = calibrate_periods()
    return {
        **({"period_evidence_cases": period_rows} if grader_version >= 19 else {}),
        "grader_version": grader_version,
        "passed": all(r["passed"] for r in rows + period_rows),
        "label_review": "engineering_labels_pending_independent_review",
        "cases": rows,
    }
