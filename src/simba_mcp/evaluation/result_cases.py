"""Publishable saved-result fixtures with independently stated expected facts."""

from copy import deepcopy
from random import Random

from .contracts import Case, Exchange, Step


def saved_results():
    """Synthetic GBP results, deliberately unequal spend and mixed section sizes."""
    return {
        "model_hash": "result-example",
        "meta": {
            "window": {"start": "2025-01-01", "end": "2025-02-28"},
            "unit": "GBP",
            "aggregation": {"ROI": "sum(Revenue)/sum(Spend)"},
            "not_windowed": ["mroi_summary"],
        },
        "warnings": ["Synthetic evidence; no scientific validity claim."],
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
            "model_config": {"link": "log", "attribution": "removal_lift"},
            "model_stats": {"available": False, "reason": "not_saved"},
            "r_hat": {"available": False, "reason": "not_saved"},
            "mroi_summary": {
                "hdi_prob": 0.94,
                "channels": [
                    {
                        "channel": "Search Activity",
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


def selected_payload(sections, *, fixture=None):
    """Model supported section projection only, not backend maths or audit storage."""
    payload = deepcopy(fixture) if fixture is not None else saved_results()
    available = payload["sections_available"]
    if not set(sections) <= set(available):
        raise ValueError("Unsupported synthetic section")
    payload["results"] = {k: v for k, v in payload["results"].items() if k in sections}
    if "mroi_periods" in sections:
        payload["results"]["mroi_periods"] = {
            "available": False,
            "reason": "fitted_before_mroi_periods",
        }
    if "prediction_window" in sections:
        payload["results"]["prediction_window"] = {"available": False, "reason": "not_saved"}
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
    for row, spend, ratio in zip(rows["coefficients"], period_spend, period_ratio, strict=True):
        row.update(Spend=float(spend), Revenue=spend * ratio, ROI=ratio)
    search_spend = sum(period_spend)
    search_revenue = sum(s * r for s, r in zip(period_spend, period_ratio, strict=True))
    rows["channel_summary"][0].update(
        Spend=float(search_spend),
        Revenue=search_revenue,
        ROI=search_revenue / search_spend,
    )
    tv_spend, tv_ratio = rng.randrange(5, 20) * 40, rng.choice((0.75, 1.25, 2.25, 3.25))
    rows["channel_summary"][1].update(
        Spend=float(tv_spend),
        Revenue=tv_spend * tv_ratio,
        ROI=tv_ratio,
    )
    median = rng.choice((0.8, 1.2, 1.8, 2.4))
    rows["mroi_summary"]["channels"][0].update(
        mroi_median=median,
        mroi_hdi_3=round(median / 2, 2),
        mroi_hdi_97=round(median * 1.5, 2),
    )
    overlap = -float(rng.randrange(3, 10))
    rows["contributions"][0].update(Overlap=overlap, Model=112 + overlap)
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
                    {"Channel": "Search Activity", "Revenue": 500.0, "Spend": 200.0, "ROI": 2.5},
                    {"Channel": "TV_activity", "Revenue": 300.0, "Spend": 100.0, "ROI": 3.0},
                ]
            },
            {"start": "2025-01-01", "end": "2025-02-28", "granularity": "native"},
        ),
        (
            "missing",
            "model_stats,r_hat",
            {"model_stats": {"available": False, "reason": "not_saved"}},
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
            {"prediction_window": {"available": False, "reason": "not_saved"}},
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
                                response=selected_payload(sections.split(",")),
                            )
                        ],
                        expected={"results": deepcopy(expected), "meta": {"unit": "GBP"}},
                    )
                ],
            )
        )
    return suite
