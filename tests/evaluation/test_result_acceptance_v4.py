"""Released V4 contract checks; no provider or backend execution."""

from fractions import Fraction

from simba_mcp.evaluation.result_acceptance_v4 import (
    ORACLE,
    A,
    B,
    acceptance_v4_tasks,
    verify,
)
from simba_mcp.evaluation.result_cases import selected_payload


def test_independent_oracle_and_family_coverage():
    assert verify()["status"] == "PASS"
    tasks = acceptance_v4_tasks()
    assert len(tasks) == len({task.family for task in tasks}) == 10
    assert len({task.dataset for task in tasks}) == 2
    assert ORACLE["audio_full_roi"] == Fraction(11, 6)
    assert tasks[0].expected["audio_roi"] == 1.875


def test_window_uses_native_boundaries_and_recomputes_ratios():
    result = selected_payload(
        ["channel_summary"], fixture=A, start="2025-02-10", end="2025-02-17", granularity="native"
    )
    rows = result["results"]["channel_summary"]
    assert [(r["Spend"], r["Revenue"], r["ROI"]) for r in rows] == [
        (270, 270, 1),
        (200, 375, 1.875),
    ]
    assert result["meta"]["window"]["start"] == "2025-02-10"


def test_monthly_prediction_totals_omit_intervals_and_keep_native_window():
    result = selected_payload(
        ["actual_vs_model"], fixture=B, start="2025-06-02", end="2025-06-23", granularity="month"
    )
    assert result["results"]["actual_vs_model"] == [
        {"period_start": "2025-06-01", "period_end": "2025-06-30", "Actual": 264, "Model": 260}
    ]
    assert result["meta"]["window"] == {
        "start": "2025-06-02",
        "end": "2025-06-23",
        "granularity": "month",
    }
    assert "actual_vs_model" not in result["meta"]["not_windowed"]


def test_native_actual_window_and_optional_authority():
    result = selected_payload(["actual_vs_model"], fixture=B, start="2025-06-09", end="2025-06-16")
    assert [r["Actual"] for r in result["results"]["actual_vs_model"]] == [71, 81]
    default = selected_payload([], fixture=A)["results"]
    assert "prediction_window" not in default and "mroi_periods" not in default
    task = acceptance_v4_tasks()[-1]
    assert task.allowed_result_sections is None
    assert not task.allow_prediction


def test_section_windows_preserve_distinct_requested_evidence_scopes():
    signed, absence = acceptance_v4_tasks()[2:4]
    assert signed.evidence_window is None
    assert signed.section_windows == {
        "contributions": {"start": "2025-02-03", "end": "2025-02-10", "granularity": "native"}
    }
    assert absence.section_windows == {
        "contributions": {"start": "2025-06-02", "end": "2025-06-02", "granularity": "native"}
    }
    for task, count in ((signed, 2), (absence, 1)):
        selected = selected_payload(
            ["contributions"], fixture=task.fixture, **task.section_windows["contributions"]
        )
        assert len(selected["results"]["contributions"]) == count
        assert len(task.fixture["results"]["contributions"]) == 4
    diagnostic = acceptance_v4_tasks()[8]
    assert diagnostic.evidence_options == (
        frozenset({"r_hat"}),
        frozenset({"model_stats", "posterior"}),
    )


def test_monthly_default_and_bundled_sections_keep_totals_and_unwindowed_evidence():
    monthly = selected_payload([], fixture=B, granularity="month")
    results = monthly["results"]
    coefficients = {r["Channel"]: r for r in results["coefficients"]}
    assert coefficients["Retail Radio_activity"]["Spend"] == 320
    assert coefficients["Retail Radio_activity"]["Revenue"] == 480
    assert coefficients["Retail Radio_activity"]["ROI"] == 1.5
    assert coefficients["Cinema_activity"]["Spend"] == 256
    assert coefficients["Cinema_activity"]["Revenue"] == 320
    assert coefficients["Cinema_activity"]["ROI"] == 1.25
    assert all("Date" not in row for row in results["coefficients"])
    assert results["channel_summary"] == B["results"]["channel_summary"]
    assert results["contributions"][0]["Model"] == 260
    assert results["contributions"][0]["Actual"] == 264
    assert results["mroi_summary"] == B["results"]["mroi_summary"]
    assert "mroi_summary" in monthly["meta"]["not_windowed"]
    assert "mroi_periods" not in results
    bundled = selected_payload(
        ["coefficients", "contributions", "actual_vs_model", "mroi_periods"],
        fixture=B,
        start="2025-06-09",
        end="2025-06-16",
        granularity="month",
    )
    assert bundled["results"]["actual_vs_model"][0]["Actual"] == 152
    assert bundled["results"]["contributions"][0]["Model"] == 150
    assert bundled["results"]["mroi_periods"] == B["results"]["mroi_periods"]
    assert bundled["meta"]["window"]["start"] == "2025-06-09"


def test_monthly_signed_components_and_ratios_reconcile():
    results = selected_payload([], fixture=A, granularity="month")["results"]
    row = results["contributions"][0]
    assert row["Overlap"] == -12
    assert row["temperature"] == -11
    assert row["Model"] == 490
    keys = set(row) - {"period_start", "period_end", "Model", "Actual", "Fit Actual"}
    assert sum(row[key] for key in keys) == row["Model"]
    coefficients = {r["Channel"]: r for r in results["coefficients"]}
    assert coefficients["Leaflet_activity"]["ROI"] == 1.5
    assert coefficients["Podcast_activity"]["ROI"] == 550 / 300


def test_week_buckets_use_declared_monday_sunday_assumption():
    result = selected_payload(
        ["contributions", "coefficients"],
        fixture=A,
        start="2025-02-03",
        end="2025-02-10",
        granularity="week",
    )
    contributions = result["results"]["contributions"]
    assert [(r["period_start"], r["period_end"]) for r in contributions] == [
        ("2025-02-03", "2025-02-09"),
        ("2025-02-10", "2025-02-16"),
    ]
    assert [r["Model"] for r in contributions] == [100, 130]
    assert [r["Overlap"] for r in contributions] == [-8, 5]
    assert len(result["results"]["coefficients"]) == 4
    assert result["meta"]["window"]["end"] == "2025-02-10"


def test_calendar_quarter_totals_and_bounds():
    result = selected_payload([], fixture=B, granularity="quarter")
    actual = result["results"]["actual_vs_model"]
    assert actual == [
        {"period_start": "2025-04-01", "period_end": "2025-06-30", "Actual": 264, "Model": 260}
    ]
    assert result["results"]["contributions"][0]["Model"] == 260
    assert len(result["results"]["coefficients"]) == 2
    assert result["results"]["mroi_summary"] == B["results"]["mroi_summary"]
