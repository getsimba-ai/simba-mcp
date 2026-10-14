"""Routing case contracts and deterministic scoring, without provider execution.

Routing scores cannot establish complete-task quality or scientific acceptance.
Case authorship and review are recorded rather than inferred from a passing score.
"""

import math
from collections import Counter
from typing import Literal

from pydantic import Field, model_validator

from ..guidance.routing import CHOICES, RoutingResult, validate_request
from .contracts import StrictModel
from .experiments import fingerprint

GRADER_VERSION = "routing-grader-v1"


class RoutingCase(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    request: str
    family: str = Field(min_length=1)
    split: Literal["development", "selection_validation", "final_acceptance"]
    provenance: str = Field(min_length=1)
    author: str = Field(min_length=1)
    reviewer: str | None = None
    label_status: Literal["proposed", "verified"] = "proposed"
    expected_choices: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)
    eligible_single_domain: bool

    @model_validator(mode="after")
    def valid_case(self):
        validate_request(self.request)
        if len(set(self.expected_choices)) != len(self.expected_choices) or any(
            value not in CHOICES for value in self.expected_choices
        ):
            raise ValueError("Expected choices must be unique documented categories")
        if self.label_status == "verified" and (not self.reviewer or self.reviewer == self.author):
            raise ValueError("Verified labels require a distinct recorded reviewer")
        if self.eligible_single_domain and any(
            choice in ("mixed_or_unclear", "unsupported") for choice in self.expected_choices
        ):
            raise ValueError("Single-domain eligibility conflicts with fallback labels")
        return self


def grade_routing(case: RoutingCase, result: dict | None, *, error: str | None = None):
    """Score one preserved attempt; never convert absent or malformed evidence to pass."""
    base = {
        "case_id": case.id,
        "case_sha256": fingerprint(case.model_dump()),
        "grader_version": GRADER_VERSION,
        "split": case.split,
        "label_status": case.label_status,
        "family": case.family,
        "eligible_single_domain": case.eligible_single_domain,
        "expected_choices": list(case.expected_choices),
    }
    if error:
        return {**base, "status": "EXECUTION_ERROR", "reason": "execution_failed"}
    if result is None:
        return {**base, "status": "NOT_RUN", "reason": "missing_attempt"}
    try:
        parsed = RoutingResult.model_validate(result)
        digest = fingerprint(result)
    except (ValueError, TypeError):
        return {**base, "status": "EXECUTION_ERROR", "reason": "invalid_result"}
    base["result_sha256"] = digest
    base["selected_choice"] = parsed.workflow
    base["confidence"] = parsed.confidence
    base["outcome"] = parsed.outcome
    if case.label_status != "verified":
        return {**base, "status": "NEEDS_REVIEW", "reason": "unverified_label"}
    if parsed.outcome == "fallback":
        return {**base, "status": "FAIL", "reason": "abstained", "routed": False}
    correct = parsed.workflow in case.expected_choices
    return {
        **base,
        "status": "PASS" if correct else "FAIL",
        "reason": "label_match" if correct else "label_mismatch",
        "routed": parsed.outcome == "recommended",
        "correct": correct,
        "eligible_single_domain": case.eligible_single_domain,
    }


def _rate(successes, total):
    """Observed proportion and 95% Wilson interval; no claim of model calibration."""
    if total == 0:
        return {"numerator": successes, "denominator": 0, "rate": None, "interval_95": None}
    z = 1.959963984540054
    p = successes / total
    divisor = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / divisor
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / divisor
    return {
        "numerator": successes,
        "denominator": total,
        "rate": p,
        "interval_95": [max(0, centre - radius), min(1, centre + radius)],
    }


def summarise_routing(scores):
    """One preserved attempt per case. Repeated trials are not independent cases."""
    ids = [row["case_id"] for row in scores]
    if len(set(ids)) != len(ids):
        raise ValueError("Summary requires one attempt per independent case")
    reviewed = [row for row in scores if row["label_status"] == "verified"]
    routed = [row for row in reviewed if row.get("routed")]
    eligible = [row for row in reviewed if row["eligible_single_domain"]]
    classified = [row for row in reviewed if type(row.get("correct")) is bool]
    confusion = Counter(
        ("|".join(sorted(row["expected_choices"])), row.get("selected_choice") or "abstained")
        for row in reviewed
        if row.get("result_sha256")
    )
    return {
        "grader_version": GRADER_VERSION,
        "counts": dict(Counter(row["status"] for row in scores)),
        "routed_precision": _rate(sum(row["status"] == "PASS" for row in routed), len(routed)),
        "single_domain_coverage": _rate(
            sum(bool(row.get("routed")) for row in eligible), len(eligible)
        ),
        "reviewed_case_count": len(reviewed),
        "unreviewed_case_count": len(scores) - len(reviewed),
        "category_confusions": [
            {"expected_choices": expected.split("|"), "selected_choice": selected, "count": count}
            for (expected, selected), count in sorted(confusion.items())
        ],
        "confidence_reliability": {
            "all_classified": _confidence_bins(classified),
            "routed": _confidence_bins([row for row in classified if row.get("routed")]),
            "limitations": (
                "Observed accuracy by separate confidence score, not option-probability calibration. "
                "Backend abstentions omit confidence; these bins condition on returned classifications. "
                "Proposed labels, missing attempts and execution errors cannot populate accuracy bins."
            ),
        },
        "score_sha256": fingerprint(scores),
        "acceptance": "NOT_ESTABLISHED",
        "boundary": "Routing classification only; not complete-task or scientific acceptance",
    }


def _confidence_bins(rows):
    """Ten fixed score bins; confidence is not equated to choice probability."""
    binned = [[] for _ in range(10)]
    for row in rows:
        confidence = row.get("confidence")
        if (
            type(confidence) not in (int, float)
            or not math.isfinite(confidence)
            or not 0 <= confidence <= 1
        ):
            raise ValueError("Classified score requires bounded finite confidence")
        binned[min(9, int(confidence * 10))].append(row)
    return [
        {
            "lower": index / 10,
            "upper": (index + 1) / 10,
            "upper_inclusive": index == 9,
            "mean_confidence": sum(row["confidence"] for row in members) / len(members)
            if members
            else None,
            "observed_accuracy": _rate(sum(row["correct"] for row in members), len(members)),
        }
        for index, members in enumerate(binned)
    ]
