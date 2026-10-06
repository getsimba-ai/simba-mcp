"""Labelled calibration of the routing scorer, not a provider benchmark."""

import pytest

from simba_mcp.evaluation.routing import RoutingCase, grade_routing, summarise_routing
from simba_mcp.guidance.routing import fallback


def case(**changes):
    return RoutingCase.model_validate(
        {
            "id": "roi_saved",
            "request": "Explain ROI from my saved model",
            "family": "results",
            "split": "development",
            "provenance": "synthetic grader calibration",
            "author": "fixture-author",
            "reviewer": "fixture-reviewer",
            "label_status": "verified",
            "expected_choices": ["results"],
            "rationale": "Existing evidence interpretation, no model creation",
            "eligible_single_domain": True,
            **changes,
        }
    )


def result(workflow="results", outcome="recommended"):
    return {
        "schema_version": 1,
        "routing_version": "workflow-v1",
        "outcome": outcome,
        "workflow": workflow,
        "confidence": 0.96,
    }


def test_correct_incorrect_and_abstention_are_distinct():
    assert grade_routing(case(), result())["status"] == "PASS"
    assert grade_routing(case(), result("mmm"))["status"] == "FAIL"
    scored = grade_routing(case(), fallback("low_confidence"))
    assert scored["reason"] == "abstained" and not scored["routed"]


def test_missing_execution_invalid_and_unreviewed_evidence_never_pass():
    assert grade_routing(case(), None)["status"] == "NOT_RUN"
    assert grade_routing(case(), None, error="timeout")["status"] == "EXECUTION_ERROR"
    assert grade_routing(case(), {"outcome": "recommended"})["status"] == "EXECUTION_ERROR"
    assert (
        grade_routing(case(label_status="proposed", reviewer=None), result())["status"]
        == "NEEDS_REVIEW"
    )


def test_review_provenance_cannot_self_verify():
    with pytest.raises(ValueError, match="distinct"):
        case(reviewer="fixture-author")


def test_mixed_and_unsupported_are_valid_correct_non_routed_answers():
    for category, outcome in [
        ("mixed_or_unclear", "clarification_needed"),
        ("unsupported", "unsupported"),
    ]:
        scored = grade_routing(
            case(expected_choices=[category], eligible_single_domain=False),
            result(category, outcome),
        )
        assert scored["status"] == "PASS" and not scored["routed"]


def test_digests_bind_labels_and_original_results():
    score = grade_routing(case(), result())
    changed = grade_routing(case(expected_choices=["mmm"]), result())
    assert score["case_sha256"] != changed["case_sha256"]
    assert score["result_sha256"] == changed["result_sha256"]


def test_development_packet_is_complete_unique_and_not_acceptance_evidence():
    from simba_mcp.evaluation.routing_cases import development_cases

    cases = development_cases()
    assert len(cases) == 80
    assert len({item.id for item in cases}) == len({item.request for item in cases}) == 80
    assert len({item.family for item in cases}) == 10
    assert all(item.split == "development" and item.label_status == "proposed" for item in cases)
    assert all(grade_routing(item, result())["status"] == "NEEDS_REVIEW" for item in cases)


def test_summary_denominators_include_missing_and_failed_eligible_cases():
    scores = [
        grade_routing(case(id="correct_case"), result()),
        grade_routing(case(id="wrong_case"), result("mmm")),
        grade_routing(case(id="absent_case"), None),
        grade_routing(case(id="timeout_case"), None, error="timeout"),
        grade_routing(case(id="fallback_case"), fallback("low_confidence")),
    ]
    report = summarise_routing(scores)
    assert report["routed_precision"]["rate"] == 0.5
    assert report["single_domain_coverage"]["rate"] == 0.4
    assert report["single_domain_coverage"]["denominator"] == 5
    assert report["acceptance"] == "NOT_ESTABLISHED"
    low, high = report["routed_precision"]["interval_95"]
    assert low < 0.5 < high


def test_summary_does_not_treat_unreviewed_labels_or_repetitions_as_evidence():
    score = grade_routing(case(label_status="proposed", reviewer=None), result())
    report = summarise_routing([score])
    assert report["routed_precision"]["rate"] is None
    assert report["unreviewed_case_count"] == 1
    assert not report["category_confusions"]
    assert all(
        bin["observed_accuracy"]["denominator"] == 0
        for bin in report["confidence_reliability"]["routed"]
    )
    with pytest.raises(ValueError, match="one attempt"):
        summarise_routing([score, score])


def test_confusion_and_confidence_bins_use_reviewed_labels_and_include_confident_errors():
    scores = [
        grade_routing(case(id="correct_case"), result()),
        grade_routing(case(id="wrong_case"), result("mmm")),
        grade_routing(case(id="missing_case"), None),
        grade_routing(case(id="unreviewed_case", label_status="proposed", reviewer=None), result()),
        grade_routing(case(id="abstained_case"), fallback("low_confidence")),
    ]
    report = summarise_routing(scores)
    last = report["confidence_reliability"]["routed"][-1]
    assert last["mean_confidence"] == 0.96
    assert last["observed_accuracy"]["rate"] == 0.5
    assert last["observed_accuracy"]["denominator"] == 2
    assert report["category_confusions"] == [
        {"expected_choices": ["results"], "selected_choice": "abstained", "count": 1},
        {"expected_choices": ["results"], "selected_choice": "mmm", "count": 1},
        {"expected_choices": ["results"], "selected_choice": "results", "count": 1},
    ]


def test_confidence_one_is_in_last_bin_and_alternatives_are_not_forced_into_one_label():
    answer = {**result("priors"), "confidence": 1.0}
    score = grade_routing(case(expected_choices=["results", "priors"]), answer)
    report = summarise_routing([score])
    assert report["confidence_reliability"]["routed"][-1]["observed_accuracy"]["rate"] == 1
    assert report["category_confusions"][0]["expected_choices"] == ["priors", "results"]


def test_selection_packet_is_separate_and_labels_are_not_self_verified():
    from simba_mcp.evaluation.routing_cases import development_cases, selection_validation_cases

    development = development_cases()
    validation = selection_validation_cases()
    assert len(validation) == 120
    assert (
        len({item.id for item in validation}) == len({item.request for item in validation}) == 120
    )
    assert not ({item.id for item in development} & {item.id for item in validation})
    assert not ({item.request for item in development} & {item.request for item in validation})
    assert all(
        item.split == "selection_validation" and item.label_status == "proposed"
        for item in validation
    )
