"""Publishable saved-result fixtures with independently stated expected facts."""

from copy import deepcopy
from datetime import UTC, datetime
from random import Random

from .contracts import Case, Exchange, Step

FIXTURE_VERSION = 2
NATIVE_WINDOW = {"start": "2025-01-01", "end": "2025-02-28"}


def saved_results():
    """Synthetic GBP results, deliberately unequal spend and mixed section sizes."""
    payload = {
        "model_hash": "result-example",
        "status": "complete",
        "model_type": "mmm",
        "sections_available": [
            "channel_summary",
            "channel_map",
            "coefficients",
            "contributions",
            "model_config",
            "model_stats",
            "r_hat",
            "response_curves",
            "mroi_summary",
            "mroi_periods",
            "prediction_window",
        ],
        "results": {
            "channel_summary": [
                {"Channel": "Search Activity", "Revenue": 500.0, "Spend": 200.0, "ROI": 2.5},
                {"Channel": "TV_activity", "Revenue": 300.0, "Spend": 100.0, "ROI": 3.0},
            ],
            "channel_map": [
                {
                    "channel": "Search",
                    "activity_column": "Search Activity",
                    "spend_column": "search_spend",
                },
                {"channel": "TV", "activity_column": "TV_activity", "spend_column": "tv_spend"},
            ],
            "coefficients": [
                {
                    "Date": 1735689600000,
                    "Channel": "Search Activity",
                    "Revenue": 200.0,
                    "Spend": 50.0,
                    "ROI": 4.0,
                },
                {
                    "Date": 1738368000000,
                    "Channel": "Search Activity",
                    "Revenue": 300.0,
                    "Spend": 150.0,
                    "ROI": 2.0,
                },
            ],
            "contributions": [
                {
                    "Date": 1735689600000,
                    "Search Activity": 20.0,
                    "TV_activity": 15.0,
                    "Base": 80.0,
                    "price": -3.0,
                    "Overlap": -2.0,
                    "Model": 110.0,
                },
            ],
            "model_config": {"config": {"link": "log", "attribution": "removal_lift"}},
            "model_stats": [{"Test Name": "Max R_hat", "Output": "1.010", "Status": "success"}],
            "r_hat": [{"Parameter": "search_activity", "R_hat": 1.01}],
            "mroi_summary": {
                "hdi_prob": 0.94,
                "evaluation_point": "current_spend",
                "spend_convention": "mean_active_period",
                "channels": [
                    {
                        "channel": "Search",
                        "activity_column": "Search Activity",
                        "current_spend": 100.0,
                        "mroi_median": 1.4,
                        "mroi_hdi_3": 0.7,
                        "mroi_hdi_97": 2.1,
                    },
                ],
            },
            "response_curves": [
                {
                    "Spend": float(i),
                    "Search Activity": i * 2.0,
                    "Search Activity_lower": i * 1.5,
                    "Search Activity_lower_50": i * 1.8,
                    "Search Activity_upper_50": i * 2.2,
                    "Search Activity_upper": i * 2.5,
                    "TV_activity": i * 3.0,
                }
                for i in range(100)
            ],
        },
    }
    rows = payload["results"]
    rows["coefficients"].extend(
        {"Date": date, "Channel": "TV_activity", "Revenue": 150.0, "Spend": 50.0, "ROI": 3.0}
        for date in (1735689600000, 1738368000000)
    )
    # A declared synthetic revenue multiplier of ten keeps revenue and KPI units distinct.
    for row in rows["coefficients"] + rows["channel_summary"]:
        row["Sales"] = row["Revenue"] / 10
    rows["contributions"].append(
        {**rows["contributions"][0], "Date": 1738368000000, "Search Activity": 30.0, "Model": 120.0}
    )
    payload["sections_available"] = list(rows)
    return payload


def selected_payload(sections, *, fixture=None, start="", end="", granularity=""):
    """Synthetic native-window contract; no fits, bucketing or audit-store emulation.

    Unknown and absent sections are omitted, as observed in live responses. This
    supports native windows only; unsupported fixture capabilities raise locally.
    """
    payload = deepcopy(fixture) if fixture is not None else saved_results()
    if granularity not in ("", "native"):
        raise ValueError("Synthetic fixture only supports native granularity")
    rows = payload["results"]
    if start or end or granularity:
        lower = (
            datetime.fromisoformat(start).replace(tzinfo=UTC).timestamp() * 1000
            if start
            else float("-inf")
        )
        upper = (
            datetime.fromisoformat(end).replace(tzinfo=UTC).timestamp() * 1000
            if end
            else float("inf")
        )
        if lower > upper:
            raise ValueError("start must not be after end")
        for section in ("coefficients", "contributions"):
            if section in rows:
                rows[section] = [r for r in rows[section] if lower <= r["Date"] <= upper]
        totals = {}
        for row in rows.get("coefficients", []):
            total = totals.setdefault(
                row["Channel"],
                {"Channel": row["Channel"], "Revenue": 0.0, "Spend": 0.0, "Sales": 0.0},
            )
            for key in ("Revenue", "Spend", "Sales"):
                total[key] += row[key]
        for total in totals.values():
            total["ROI"] = total["Revenue"] / total["Spend"] if total["Spend"] else 0.0
        rows["channel_summary"] = list(totals.values())
    selected = set(sections) if sections else set(rows) - {"mroi_periods", "prediction_window"}
    payload["results"] = {k: v for k, v in rows.items() if k in selected}
    if "mroi_periods" in sections:
        payload["results"].setdefault(
            "mroi_periods",
            {
                "available": False,
                "reason": "fitted_before_mroi_periods",
            },
        )
    payload["sections_available"] = list(payload["results"])
    for optional in ("mroi_periods", "prediction_window"):
        if (
            optional in rows
            and optional not in selected
            and (optional != "mroi_periods" or rows[optional].get("available"))
        ):
            payload["sections_available"].append(optional)
    if start or end or granularity:
        payload["meta"] = {
            "window": {"start": start or None, "end": end or None, "granularity": "native"},
            "aggregation": {"channel_summary": "ROI = sum(Revenue) / sum(Spend); 0 without spend"},
            "not_windowed": {
                k: "mROI is not re-aggregated; rows returned as fitted"
                if k == "mroi_periods"
                else "not a per-period section"
                for k in payload["results"]
                if k not in ("coefficients", "contributions", "channel_summary")
            },
        }
    return payload


def varied_results(seed):
    """Fresh numerical evidence; generated after guidance selection, never a fit.

    These variants test transfer beyond memorised development values. They are
    procedurally generated validation, not externally authored hidden benchmarks.
    """
    rng = Random(seed)
    payload = saved_results()
    rows = payload["results"]
    period_spend = (rng.randrange(4, 12) * 25, rng.randrange(15, 30) * 25)
    period_ratio = (rng.choice((1.5, 2.0, 3.5, 4.5)), rng.choice((0.5, 1.0, 2.5, 3.0)))
    for row, spend, ratio in zip(rows["coefficients"][:2], period_spend, period_ratio, strict=True):
        row.update(Spend=float(spend), Revenue=spend * ratio, Sales=spend * ratio / 10, ROI=ratio)
    search_spend = sum(period_spend)
    search_revenue = sum(s * r for s, r in zip(period_spend, period_ratio, strict=True))
    rows["channel_summary"][0].update(
        Spend=float(search_spend),
        Revenue=search_revenue,
        Sales=search_revenue / 10,
        ROI=search_revenue / search_spend,
    )
    tv_spend, tv_ratio = rng.randrange(5, 20) * 40, rng.choice((0.75, 1.25, 2.25, 3.25))
    rows["channel_summary"][1].update(
        Spend=float(tv_spend),
        Revenue=tv_spend * tv_ratio,
        Sales=tv_spend * tv_ratio / 10,
        ROI=tv_ratio,
    )
    for row in rows["coefficients"][2:]:
        row.update(
            Spend=tv_spend / 2,
            Revenue=tv_spend * tv_ratio / 2,
            Sales=tv_spend * tv_ratio / 20,
            ROI=tv_ratio,
        )
    median = rng.choice((0.8, 1.2, 1.8, 2.4))
    rows["mroi_summary"]["channels"][0].update(
        mroi_median=median,
        current_spend=search_spend / 2,
        mroi_hdi_3=round(median / 2, 2),
        mroi_hdi_97=round(median * 1.5, 2),
    )
    overlap = float(rng.choice((-1, 1)) * rng.randrange(3, 10))
    for i, row in enumerate(rows["contributions"]):
        row.update(
            {
                "Search Activity": rows["coefficients"][i]["Sales"],
                "TV_activity": rows["coefficients"][i + 2]["Sales"],
                "Overlap": overlap,
            }
        )
        row["Model"] = sum(
            row[k] for k in ("Search Activity", "TV_activity", "Base", "price", "Overlap")
        )
    return payload


def result_cases():
    """Exact requests test forwarding; expected facts are not computed by the handler."""
    suite = []
    for name, sections, expected, extra in [
        (
            "roi",
            "channel_summary,channel_map",
            {
                "channel_summary": [
                    {
                        "Channel": "Search Activity",
                        "Revenue": 500.0,
                        "Spend": 200.0,
                        "Sales": 50.0,
                        "ROI": 2.5,
                    },
                    {
                        "Channel": "TV_activity",
                        "Revenue": 300.0,
                        "Spend": 100.0,
                        "Sales": 30.0,
                        "ROI": 3.0,
                    },
                ]
            },
            {"start": "2025-01-01", "end": "2025-02-28", "granularity": "native"},
        ),
        (
            "missing",
            "model_stats,r_hat",
            {"model_stats": [{"Test Name": "Max R_hat", "Output": "1.010", "Status": "success"}]},
            {},
        ),
        (
            "old",
            "mroi_periods",
            {"mroi_periods": {"available": False, "reason": "fitted_before_mroi_periods"}},
            {},
        ),
        ("marginal", "mroi_summary", {"mroi_summary": {"hdi_prob": 0.94}}, {}),
        (
            "prediction",
            "prediction_window",
            {},
            {},
        ),
    ]:
        suite.append(
            Case(
                id=f"result_{name}",
                purpose="Selective saved evidence with source metadata",
                steps=[
                    Step(
                        tool="get_model_results",
                        arguments={"model_hash": "result-example", "sections": sections, **extra},
                        exchanges=[
                            Exchange(
                                method="GET",
                                path="/api/v1/models/result-example/results",
                                query={"format": "json", "sections": sections, **extra},
                                response=selected_payload(sections.split(","), **extra),
                            )
                        ],
                        expected={"results": deepcopy(expected)},
                    )
                ],
            )
        )
    return suite
