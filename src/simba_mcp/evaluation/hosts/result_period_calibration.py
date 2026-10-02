"""Hand-labelled prospective monthly-evidence calibration, no provider or dispatch."""

from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace

from .result_period_evidence import monthly_evidence


def period_fixture():
    def row(day, revenue, spend):
        return {
            "Date": datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp() * 1000,
            "Channel": "activity_a",
            "Revenue": revenue,
            "Spend": spend,
            "Sales": revenue / 10,
            "ROI": revenue / spend,
        }

    return {
        "model_hash": "calibration-periods",
        "results": {
            "channel_map": [{"channel": "Media A", "activity_column": "activity_a"}],
            "coefficients": [
                row("2025-01-01", 100, 20),
                row("2025-01-08", 300, 80),
                row("2025-02-01", 200, 100),
            ],
        },
    }


def period_labels():
    task = SimpleNamespace(
        fixture=period_fixture(),
        channel="activity_a",
        evidence_window={"start": "2025-01-01", "end": "2025-02-28"},
    )
    window = {**task.evidence_window, "granularity": "month"}
    first = {
        "period_start": "2025-01-01",
        "period_end": "2025-01-31",
        "Channel": "activity_a",
        "Revenue": 400,
        "Spend": 100,
        "ROI": 4,
    }
    second = {
        "period_start": "2025-02-01",
        "period_end": "2025-02-28",
        "Channel": "activity_a",
        "Revenue": 200,
        "Spend": 100,
        "ROI": 2,
    }
    payload = {
        "model_hash": "calibration-periods",
        "meta": {"window": window},
        "results": {"coefficients": [first, second]},
    }
    labels = [("both_months", task, payload, window, 2)]
    for name, field, value in (
        ("wrong_channel", "Channel", "wrong"),
        ("boolean_revenue", "Revenue", True),
        ("nonfinite_revenue", "Revenue", float("inf")),
        ("averaged_roi", "ROI", 4.375),
        ("wrong_month", "period_start", "2024-12-01"),
        ("partial_bucket", "period_end", "2025-01-30"),
    ):
        bad = deepcopy(payload)
        bad["results"]["coefficients"][0][field] = value
        labels.append(
            (name, task, bad, window, 0 if name in ("wrong_month", "partial_bucket") else 1)
        )
    for name, changes in (
        ("partial_window", {"start": "2025-01-08"}),
        ("overbroad_window", {"end": "2025-03-31"}),
        ("quarter_context", {"granularity": "quarter"}),
    ):
        bad = deepcopy(payload)
        bad["meta"]["window"].update(changes)
        labels.append((name, task, bad, bad["meta"]["window"], 0))
    bad = deepcopy(payload)
    bad["meta"]["window"]["start"] = "2025-02-01"
    labels.append(("mixed_request_response_window", task, bad, window, 0))
    bad = deepcopy(payload)
    bad["model_hash"] = "other-model"
    labels.append(("wrong_model", task, bad, window, 0))
    bad = deepcopy(payload)
    bad["results"]["coefficients"] = bad["results"]["coefficients"][:1]
    labels.append(("missing_month", task, bad, window, 1))
    single = {"start": "2025-01-01", "end": "2025-01-31", "granularity": "month"}
    summary = {
        "model_hash": "calibration-periods",
        "meta": {"window": single},
        "results": {
            "channel_summary": [{k: v for k, v in first.items() if not k.startswith("period_")}]
        },
    }
    labels.append(("exact_single_month_summary", task, summary, single, 1))
    bad = deepcopy(summary)
    bad["meta"]["window"] = window
    labels.append(("two_month_summary_not_period_evidence", task, bad, window, 0))
    bad = deepcopy(summary)
    bad["results"]["channel_summary"][0]["Spend"] = True
    labels.append(("boolean_summary", task, bad, single, 0))
    bad = deepcopy(summary)
    bad["results"]["channel_summary"][0]["ROI"] = 4.375
    labels.append(("averaged_summary_roi", task, bad, single, 0))
    partial = deepcopy(task)
    partial.evidence_window = {"start": "2025-01-08", "end": "2025-02-28"}
    labels.append(("partial_task_not_full_month", partial, payload, window, 0))
    native = {
        "model_hash": "calibration-periods",
        "meta": {"window": {**window, "granularity": "native"}},
        "results": {"coefficients": deepcopy(task.fixture["results"]["coefficients"])},
    }
    labels.append(("complete_native_rows", task, native, native["meta"]["window"], 2))
    bad = deepcopy(native)
    bad["results"]["coefficients"].pop(0)
    labels.append(("missing_native_row", task, bad, bad["meta"]["window"], 1))
    bad = deepcopy(payload)
    bad["results"]["coefficients"].append({**first, "Revenue": 999})
    labels.append(("contradictory_duplicate_bucket", task, bad, window, 1))
    bad = deepcopy(payload)
    bad["results"]["coefficients"].append(dict(first))
    labels.append(("identical_duplicate_bucket", task, bad, window, 2))
    bad = deepcopy(summary)
    bad["results"]["channel_summary"].append(
        {**bad["results"]["channel_summary"][0], "Revenue": 999}
    )
    labels.append(("contradictory_duplicate_summary", task, bad, single, 0))
    bad = deepcopy(summary)
    bad["results"]["coefficients"] = [dict(first)]
    bad["results"]["channel_summary"][0]["Revenue"] = 999
    labels.append(("coefficient_summary_conflict", task, bad, single, 0))
    bad = deepcopy(native)
    bad["results"]["coefficients"].append({**bad["results"]["coefficients"][0], "Revenue": 999})
    labels.append(("contradictory_native_duplicate", task, bad, bad["meta"]["window"], 1))
    bad = deepcopy(payload)
    bad["meta"]["window"] = {"start": "20250101", "end": "20250228", "granularity": "month"}
    labels.append(("noncanonical_window_dates", task, bad, bad["meta"]["window"], 0))
    bad = deepcopy(native)
    unexpected = deepcopy(bad["results"]["coefficients"][0])
    unexpected["Date"] += 86400000
    unexpected["Revenue"] = 999
    bad["results"]["coefficients"].append(unexpected)
    labels.append(("unexpected_native_date", task, bad, bad["meta"]["window"], 0))
    bad = deepcopy(payload)
    bad["results"]["coefficients"].append({**first, "period_start": "2025-01-02", "Revenue": 999})
    labels.append(("unexpected_shifted_bucket", task, bad, window, 0))
    return labels


def calibrate_periods():
    rows = []
    for name, task, payload, window, expected in period_labels():
        wanted, observed = monthly_evidence(task, payload, window)
        actual = len({(r["period_start"], r["period_end"], r["Channel"]) for r in observed})
        rows.append(
            {
                "id": name,
                "expected_atoms": expected,
                "actual_atoms": actual,
                "expected_months": len(wanted),
                "passed": actual == expected,
            }
        )
    return rows
