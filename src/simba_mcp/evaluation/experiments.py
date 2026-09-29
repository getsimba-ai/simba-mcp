"""Frozen experimental inputs and paired, family-clustered development estimates.

This module never calls a provider or changes a candidate. Public development
data cannot produce final acceptance, even when all descriptive gates pass.
"""

import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean

PROPOSED_THRESHOLDS = {
    "minimum_task_families": 8,
    "minimum_cost_saving": 0.05,
    "quality_noninferiority_margin": 0,
}


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def source_fingerprint():
    root = Path(__file__).parents[1]
    return fingerprint(
        {
            p.relative_to(root).as_posix(): p.read_text(encoding="utf-8").replace("\r\n", "\n")
            for p in sorted(root.rglob("*"))
            if p.is_file() and p.suffix in (".py", ".md", ".json")
        }
    )


def freeze_experiment(inputs, calibration):
    """Call before opening a provider client; retain the full reviewed inputs."""
    if not calibration or not calibration.get("passed"):
        raise ValueError("Grader calibration must pass before provider execution")
    if inputs.get("purpose") != "development":
        raise ValueError("Independent acceptance is not supported by public development cases")
    if type(inputs.get("samples")) is not int or inputs["samples"] < 2:
        raise ValueError("A paired experiment requires at least two repetitions")
    return {
        "schema_version": 1,
        "inputs_sha256": fingerprint(inputs),
        "source_sha256": source_fingerprint(),
        "calibration_sha256": fingerprint(calibration),
    }


def verify_experiment(frozen, inputs, calibration):
    if frozen != freeze_experiment(inputs, calibration):
        raise ValueError("Frozen experiment changed; stop without spending or regrading")


def assess_comparison(rows, families, *, samples, resamples=4000, seed=20260929, datasets=None):
    """Equal-weight task-family bootstrap, keeping paired repetitions together.

    Intervals describe only the sampled development families, not production
    generalisation. Missing pairs, duplicates and non-finite costs invalidate
    the comparison. Repetitions never inflate the independent family count.
    """
    if not families or any(not family for family in families.values()):
        raise ValueError("Every task requires a nonempty family")
    if samples < 2 or resamples < 100:
        raise ValueError("Need repeated pairs and at least 100 bootstrap draws")
    expected = {
        (case, rep, arm)
        for case in families
        for rep in range(samples)
        for arm in ("baseline", "candidate")
    }
    indexed = {}
    invalid = []
    for row in rows:
        key = (row.get("case"), row.get("repetition"), row.get("view"))
        if key in indexed or key not in expected:
            invalid.append("duplicate_or_unexpected_trial")
        indexed[key] = row
        cost = row.get("session", {}).get("cost_usd")
        if (
            type(cost) not in (int, float)
            or not math.isfinite(cost)
            or cost < 0
            or type(row.get("passed")) is not bool
        ):
            invalid.append("incomplete_trial")
    if set(indexed) != expected:
        invalid.append("missing_pairs")
    if invalid:
        return {"status": "invalid", "reasons": sorted(set(invalid)), "accepted": False}

    grouped = defaultdict(list)
    for case, family in families.items():
        values = []
        for rep in range(samples):
            baseline = indexed[case, rep, "baseline"]
            candidate = indexed[case, rep, "candidate"]
            values.append(
                (
                    int(candidate["passed"]) - int(baseline["passed"]),
                    baseline["session"]["cost_usd"],
                    candidate["session"]["cost_usd"],
                )
            )
        grouped[family].append(values)
    units = [
        tuple(mean(mean(v[i] for v in pairs) for pairs in cases) for i in range(3))
        for cases in grouped.values()
    ]

    def summarise(selected):
        quality = mean(v[0] for v in selected)
        base, candidate = (mean(v[i] for v in selected) for i in (1, 2))
        return quality, (1 - candidate / base) if base > 0 else None

    point = summarise(units)
    rng = random.Random(seed)
    draws = []
    for _ in range(resamples):
        selected = []
        for cases in rng.choices(list(grouped.values()), k=len(units)):
            means = []
            for pairs in cases:
                sampled_pairs = rng.choices(pairs, k=len(pairs))
                means.append(tuple(mean(v[i] for v in sampled_pairs) for i in range(3)))
            selected.append(tuple(mean(v[i] for v in means) for i in range(3)))
        draws.append(summarise(selected))

    def interval(index):
        values = sorted(v[index] for v in draws if v[index] is not None)
        if len(units) < 2 or len(values) != resamples:
            return None
        return [values[int(0.025 * (len(values) - 1))], values[int(0.975 * (len(values) - 1))]]

    quality_ci, savings_ci = interval(0), interval(1)
    candidates = [r for r in rows if r["view"] == "candidate"]
    pending_review = sum(r.get("claim_review_required", False) for r in rows)
    hard_failures = sum(
        r.get("outcome") == "fail"
        if "outcome" in r
        else not all(
            r.get("assertions", {}).get(k, False)
            for k in (
                "facts",
                "claims_in_scope",
                "required_evidence",
                "no_errors",
                "no_unintended_writes",
                "executed",
            )
        )
        for r in candidates
    )
    if pending_review:
        quality_ci = None
    reasons = [
        "public_development_cases_are_not_independent_acceptance",
        "thresholds_require_owner_agreement",
    ]
    if len(units) < PROPOSED_THRESHOLDS["minimum_task_families"]:
        reasons.append("fewer_than_eight_task_families")
    if hard_failures:
        reasons.append("candidate_quality_or_routing_failures")
    if pending_review:
        reasons.append("unreviewed_claims_prevent_quality_comparison")
    if quality_ci is None or quality_ci[0] < -PROPOSED_THRESHOLDS["quality_noninferiority_margin"]:
        reasons.append("quality_noninferiority_not_established")
    if savings_ci is None or savings_ci[0] < PROPOSED_THRESHOLDS["minimum_cost_saving"]:
        reasons.append("five_percent_cost_saving_not_established")
    return {
        "status": "development_only",
        "accepted": False,
        "reasons": reasons,
        "task_count": len(families),
        "family_count": len(units),
        "dataset_count": len(set(datasets.values())) if datasets else 1,
        "paired_repetitions": samples,
        "candidate_hard_failures": hard_failures,
        "quality_delta": None if pending_review else point[0],
        "sessions_requiring_claim_review": pending_review,
        "quality_delta_95_interval": quality_ci,
        "cost_saving_fraction": point[1],
        "cost_saving_95_interval": savings_ci,
        "bootstrap_seed": seed,
        "bootstrap_resamples": resamples,
        "weighting": "equal task families; equal cases and paired repetitions within family",
        "limitations": "Intervals condition on the synthetic datasets and task families used. "
        "Datasets are not independently resampled. These intervals do not establish "
        "dataset or scientific generalisation.",
    }
