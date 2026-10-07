"""Paired descriptive evidence cannot turn missing usage or review into savings."""

from copy import deepcopy

import pytest

from simba_mcp.evaluation.hosts.routing_report import paired_routing_report


def rows(samples=3):
    return [
        {
            "case": case,
            "view": arm,
            "repetition": repetition,
            "passed": True,
            "outcome": "pass",
            "complete_task_usage": {
                "total_input_tokens": 100 if arm == "baseline" else 80,
                "total_cost_usd": 0.1 if arm == "baseline" else 0.11,
                "seconds": 10 if arm == "baseline" else 9,
                "accounting_complete": True,
            },
            "routing_attempts": []
            if arm == "baseline"
            else [{"result": {"outcome": "fallback", "reason": "low_confidence"}}],
        }
        for case in ("a", "b")
        for repetition in range(samples)
        for arm in ("baseline", "candidate")
    ]


def report(data, **kwargs):
    return paired_routing_report(
        data, {"a": "results", "b": "campaigns"}, samples=3, resamples=100, **kwargs
    )


def test_paired_selector_inclusive_estimates_latency_and_cost_regression():
    data = rows()
    original = deepcopy(data)
    measured = report(data)
    assert measured["status"] == "descriptive_only" and not measured["accepted"]
    assert measured["paired"]["total_input_tokens"]["estimate"] == pytest.approx(0.2)
    assert measured["paired"]["total_cost_usd"]["estimate"] == pytest.approx(-0.1)
    assert measured["paired"]["seconds"]["estimate"] == pytest.approx(0.1)
    assert measured["arms"]["candidate"]["routing_calls"] == 6
    assert measured["arms"]["candidate"]["routing_outcomes"] == {"low_confidence": 6}
    assert measured["arms"]["candidate"]["metrics"]["seconds"]["p95"] == 9
    assert data == original and report(data) == measured


@pytest.mark.parametrize("fault", ["missing", "duplicate", "unknown", "nan", "bool", "error"])
def test_incomplete_pairs_do_not_establish_savings(fault):
    data = rows()
    if fault == "missing":
        data.pop()
    elif fault == "duplicate":
        data.append(deepcopy(data[0]))
    elif fault == "unknown":
        data[0]["complete_task_usage"]["accounting_complete"] = False
        data[0]["complete_task_usage"]["total_cost_usd"] = None
    elif fault in ("nan", "bool"):
        data[0]["complete_task_usage"]["total_input_tokens"] = (
            float("nan") if fault == "nan" else True
        )
    else:
        data[0]["outcome"] = "execution_error"
    measured = report(data)
    assert measured["status"] == "incomplete" and measured["paired"] is None
    assert measured["arms"]["baseline"]["expected_trials"] == 6
    assert measured["accepted"] is False


def test_claim_review_suppresses_quality_not_accounted_usage():
    data = rows()
    data[1]["claim_review_required"] = True
    data[1]["outcome"] = "review"
    data[1]["passed"] = False
    measured = report(data)
    assert measured["paired"]["measured_quality_delta"] == {"estimate": None, "interval_95": None}
    assert measured["paired"]["total_input_tokens"]["estimate"] == pytest.approx(0.2)


def test_repetitions_do_not_inflate_family_independence():
    measured = paired_routing_report(rows(), {"a": "same", "b": "same"}, samples=3, resamples=100)
    assert measured["family_count"] == 1
    assert all(metric["interval_95"] is None for metric in measured["paired"].values())
