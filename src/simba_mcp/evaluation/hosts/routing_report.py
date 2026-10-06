"""Descriptive paired routing measurements; never provider or release acceptance."""

import math
import random
from collections import Counter, defaultdict
from statistics import mean, median

from ..experiments import fingerprint

METRICS = ("total_input_tokens", "total_cost_usd", "seconds")


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _quantile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower = int(position)
    return values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (
        position - lower
    )


def paired_routing_report(rows, families, *, samples, seed=20261006, resamples=1000):
    """Pair repetitions, then bootstrap families with repetitions nested in tasks.

    Every expected trial stays in the denominator. Incomplete evidence prevents
    paired estimates. Descriptive measured quality is separate from claim review.
    Family labels are frozen inputs, not inferred from successful outputs.
    """
    if (
        not families
        or any(not isinstance(family, str) or not family for family in families.values())
        or type(samples) is not int
        or samples < 1
        or type(resamples) is not int
        or resamples < 100
        or type(seed) is not int
    ):
        raise ValueError("Paired reporting requires families, samples and a fixed bootstrap")
    expected = {
        (case, repetition, arm)
        for case in families
        for repetition in range(samples)
        for arm in ("baseline", "candidate")
    }
    indexed, invalid = {}, set()
    for row in rows:
        key = (row.get("case"), row.get("repetition"), row.get("view"))
        if key in indexed or key not in expected:
            invalid.add("duplicate_or_unexpected_trial")
        indexed[key] = row
    if set(indexed) != expected:
        invalid.add("missing_pairs")
    arms = {}
    for arm in ("baseline", "candidate"):
        selected = [row for row in rows if row.get("view") == arm]
        measured = [row.get("complete_task_usage", {}) for row in selected]
        arms[arm] = {
            "expected_trials": len(families) * samples,
            "recorded_trials": len(selected),
            "outcomes": dict(Counter(row.get("outcome", "execution_error") for row in selected)),
            "pending_claim_reviews": sum(
                bool(row.get("claim_review_required")) for row in selected
            ),
            "unintended_writes": sum(row.get("unintended_writes", 0) for row in selected),
            "routing_calls": sum(len(row.get("routing_attempts", [])) for row in selected),
            "routing_adoption_trials": sum(bool(row.get("routing_attempts")) for row in selected),
            "routing_outcomes": dict(
                Counter(
                    attempt.get("result", {}).get("reason")
                    or attempt.get("result", {}).get("outcome")
                    or attempt.get("status", "unknown")
                    for row in selected
                    for attempt in row.get("routing_attempts", [])
                )
            ),
            "unknown_accounting_trials": sum(
                usage.get("accounting_complete") is not True for usage in measured
            ),
            "metrics": {
                metric: {
                    "observed": sum(_number(usage.get(metric)) for usage in measured),
                    "p50": _quantile(
                        [usage[metric] for usage in measured if _number(usage.get(metric))], 0.5
                    ),
                    "p95": _quantile(
                        [usage[metric] for usage in measured if _number(usage.get(metric))], 0.95
                    ),
                }
                for metric in METRICS
            },
        }
    for row in indexed.values():
        usage = row.get("complete_task_usage", {})
        if (
            usage.get("accounting_complete") is not True
            or any(not _number(usage.get(metric)) for metric in METRICS)
            or row.get("outcome") not in ("pass", "fail", "review")
            or type(row.get("passed")) is not bool
        ):
            invalid.add("incomplete_trial")
    try:
        trial_hash = fingerprint(rows)
    except (ValueError, TypeError):
        trial_hash = None
        invalid.add("invalid_json_evidence")
    report = {
        "version": "paired-routing-report-v1",
        "accepted": False,
        "status": "incomplete" if invalid else "descriptive_only",
        "reasons": sorted(invalid),
        "trial_sha256": trial_hash,
        "task_count": len(families),
        "family_count": len(set(families.values())),
        "samples": samples,
        "arms": arms,
        "paired": None,
        "bootstrap_seed": seed,
        "bootstrap_resamples": resamples,
        "limitations": [
            "Synthetic selection evidence cannot establish independent acceptance",
            "Intervals condition on supplied families and fixtures",
            "Known incomplete subsets never establish a paired saving",
            "Descriptive correctness does not adjudicate pending explanatory claims",
        ],
    }
    if invalid:
        return report
    grouped = defaultdict(list)
    for case, family in families.items():
        pairs = [
            tuple(indexed[case, repetition, arm] for arm in ("baseline", "candidate"))
            for repetition in range(samples)
        ]
        grouped[family].append(pairs)

    def summarize(units):
        # Equal family weight: medians over each family's mean task measurements.
        result = {}
        for metric in METRICS:
            base = median(unit[metric][0] for unit in units)
            candidate = median(unit[metric][1] for unit in units)
            result[metric] = 1 - candidate / base if base > 0 else None
        result["measured_quality_delta"] = mean(unit["quality"] for unit in units)
        return result

    def unit(cases, rng=None):
        task_units = []
        for pairs in cases:
            pairs = rng.choices(pairs, k=len(pairs)) if rng else pairs
            task_units.append(
                {
                    **{
                        metric: tuple(
                            mean(pair[arm]["complete_task_usage"][metric] for pair in pairs)
                            for arm in (0, 1)
                        )
                        for metric in METRICS
                    },
                    "quality": mean(
                        int(pair[1]["passed"]) - int(pair[0]["passed"]) for pair in pairs
                    ),
                }
            )
        return {
            **{
                metric: tuple(mean(task[metric][arm] for task in task_units) for arm in (0, 1))
                for metric in METRICS
            },
            "quality": mean(task["quality"] for task in task_units),
        }

    point = summarize([unit(cases) for cases in grouped.values()])
    rng = random.Random(seed)
    draws = [
        summarize(
            [unit(cases, rng) for cases in rng.choices(list(grouped.values()), k=len(grouped))]
        )
        for _ in range(resamples)
    ]
    pending = any(arms[arm]["pending_claim_reviews"] for arm in arms)
    report["paired"] = {
        key: {
            "estimate": value if key != "measured_quality_delta" or not pending else None,
            "interval_95": (
                [_quantile([draw[key] for draw in draws], quantile) for quantile in (0.025, 0.975)]
                if len(grouped) > 1
                and all(draw[key] is not None for draw in draws)
                and not (pending and key == "measured_quality_delta")
                else None
            ),
        }
        for key, value in point.items()
    }
    report["weighting"] = "Equal families; mean tasks and paired repetitions within family"
    return report
