"""Prospective monthly evidence atoms, separate from native-period grading."""

import calendar
from datetime import date
from math import isfinite

from ..result_cases import selected_payload


def complete_month_window(window):
    try:
        first = date.fromisoformat(window["start"])
        last = date.fromisoformat(window["end"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        first.isoformat() == window["start"]
        and last.isoformat() == window["end"]
        and first <= last
        and first.day == 1
        and last.day == calendar.monthrange(last.year, last.month)[1]
    )


def _matches(actual, expected):
    return isinstance(actual, dict) and all(
        key in actual
        and (
            type(actual[key]) in (int, float) and isfinite(actual[key]) and actual[key] == value
            if type(value) in (int, float)
            else type(actual[key]) is type(value) and actual[key] == value
        )
        for key, value in expected.items()
    )


def monthly_evidence(task, returned, request_window, *, conflicts=None):
    """Return oracle atoms and verified atoms, never equate monthly totals to native rows."""
    conflicts = conflicts if conflicts is not None else []
    task_window = task.evidence_window or {}
    if not complete_month_window(task_window):
        return [], []
    oracle = selected_payload(
        {"coefficients"},
        fixture=task.fixture,
        start=task_window["start"],
        end=task_window["end"],
        granularity="month",
    )["results"]["coefficients"]
    fields = ("period_start", "period_end", "Channel", "Revenue", "Spend", "ROI")
    wanted = [
        {k: row[k] for k in fields}
        for row in oracle
        if not task.channel or row["Channel"] == task.channel
    ]
    first = date.fromisoformat(task_window["start"])
    last = date.fromisoformat(task_window["end"])
    months = set()
    cursor = first
    while cursor <= last:
        months.add(cursor.isoformat())
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    if {row["period_start"] for row in wanted} != months:
        return [], []
    window = returned.get("meta", {}).get("window", {})
    if (
        returned.get("model_hash") != task.fixture["model_hash"]
        or not complete_month_window(window)
        or window["start"] < task_window["start"]
        or window["end"] > task_window["end"]
        or any(
            window.get(k, "native") != request_window.get(k, "native")
            for k in ("start", "end", "granularity")
        )
        or window.get("granularity", "native") not in ("native", "month")
    ):
        return wanted, []
    results = returned.get("results", {})
    observed = []
    for target in wanted:
        if not (
            window["start"] <= target["period_start"] and window["end"] >= target["period_end"]
        ):
            continue
        conflict_before = len(conflicts)

        def accept(rows, expected, atom=target):
            if not rows:
                return False
            if not all(_matches(row, expected) for row in rows):
                conflicts.append(atom)
                return False
            return True

        supported = False
        coefficients = results.get("coefficients", [])
        channel_rows = [
            row
            for row in coefficients
            if isinstance(row, dict) and row.get("Channel") == target["Channel"]
        ]
        if window.get("granularity") == "month":
            permitted = {
                (row["period_start"], row["period_end"])
                for row in wanted
                if row["Channel"] == target["Channel"]
                and window["start"] <= row["period_start"]
                and row["period_end"] <= window["end"]
            }
            if any(
                not isinstance(row.get("period_start"), str)
                or not isinstance(row.get("period_end"), str)
                or (row.get("period_start"), row.get("period_end")) not in permitted
                for row in channel_rows
            ):
                conflicts.append(target)
        else:
            permitted_native = selected_payload(
                {"coefficients"},
                fixture=task.fixture,
                start=window["start"],
                end=window["end"],
                granularity="native",
            )["results"]["coefficients"]
            permitted_dates = {
                row["Date"] for row in permitted_native if row["Channel"] == target["Channel"]
            }
            if any(
                type(row.get("Date")) not in (int, float) or row["Date"] not in permitted_dates
                for row in channel_rows
            ):
                conflicts.append(target)
        if window.get("granularity") == "month":
            matching = [
                row
                for row in coefficients
                if isinstance(row, dict)
                and row.get("Channel") == target["Channel"]
                and row.get("period_start") == target["period_start"]
            ]
            supported = accept(matching, target)
        else:
            native = selected_payload(
                {"coefficients"},
                fixture=task.fixture,
                start=target["period_start"],
                end=target["period_end"],
                granularity="native",
            )["results"]["coefficients"]
            native = [row for row in native if row["Channel"] == target["Channel"]]
            native_matches = []
            for expected in native:
                matching = [
                    row
                    for row in coefficients
                    if isinstance(row, dict)
                    and row.get("Channel") == expected["Channel"]
                    and row.get("Date") == expected["Date"]
                ]
                native_matches.append(accept(matching, expected))
            supported = bool(native) and all(native_matches)
        if (window["start"], window["end"]) == (target["period_start"], target["period_end"]):
            summary = {k: v for k, v in target.items() if k not in ("period_start", "period_end")}
            matching = [
                row
                for row in results.get("channel_summary", [])
                if isinstance(row, dict) and row.get("Channel") == target["Channel"]
            ]
            supported = accept(matching, summary) or supported
        if supported and len(conflicts) == conflict_before:
            observed.append(target)
    return wanted, observed
