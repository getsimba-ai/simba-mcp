"""Publishable saved-result fixtures with independently stated expected facts."""

from copy import deepcopy

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


def selected_payload(sections):
    """Model supported section projection only, not backend maths or audit storage."""
    payload = saved_results()
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
