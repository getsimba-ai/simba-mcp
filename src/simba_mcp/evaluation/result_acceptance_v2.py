"""Independent synthetic saved-result acceptance cases, version two."""

from copy import deepcopy
from datetime import UTC, datetime

from simba_mcp.evaluation.hosts.result_selection import ResultTask


def _stamp(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp() * 1000)


def _garden():
    dates = [_stamp(d) for d in ("2025-04-07", "2025-04-14", "2025-04-21")]
    records = []
    for channel, values in (
        ("Leaf Activity", ((60, 180, 36), (180, 270, 54), (60, 150, 30))),
        ("Seed Activity", ((90, 180, 36), (30, 120, 24), (180, 270, 54))),
    ):
        for date, (spend, revenue, sales) in zip(dates, values):
            records.append(
                {
                    "Date": date,
                    "Channel": channel,
                    "Spend": spend,
                    "Revenue": revenue,
                    "Sales": sales,
                    "ROI": revenue / spend,
                }
            )
    return {
        "model_hash": "synthetic-garden-v2",
        "results": {
            "channel_map": [
                {
                    "channel": "Leaflets",
                    "activity_column": "Leaf Activity",
                    "spend_column": "Leaf Spend",
                },
                {
                    "channel": "Seed fairs",
                    "activity_column": "Seed Activity",
                    "spend_column": "Seed Spend",
                },
            ],
            "coefficients": records,
            "channel_summary": [
                {"Channel": "Leaf Activity", "Spend": 300, "Revenue": 600, "Sales": 120, "ROI": 2},
                {
                    "Channel": "Seed Activity",
                    "Spend": 300,
                    "Revenue": 570,
                    "Sales": 114,
                    "ROI": 1.9,
                },
            ],
            "mroi_summary": {
                "hdi_prob": 0.94,
                "channels": [
                    {
                        "channel": "Leaflets",
                        "activity_column": "Leaf Activity",
                        "current_spend": 100,
                        "mroi_mean": 1.7,
                        "mroi_median": 1.3,
                        "mroi_hdi_3": 0.6,
                        "mroi_hdi_97": 2.4,
                    }
                ],
            },
            "mroi_periods": {
                "available": True,
                "hdi_prob": 0.94,
                "evaluation_point": "historical_period_spend",
                "rows": [
                    {
                        "channel": "Leaflets",
                        "activity_column": "Leaf Activity",
                        "date": d,
                        "spend": s,
                        "mroi_median": m,
                        "mroi_hdi_3": lo,
                        "mroi_hdi_97": hi,
                    }
                    for d, s, m, lo, hi in [
                        ("2025-04-07", 60, 1.9, 1.1, 2.7),
                        ("2025-04-14", 180, 0.8, 0.2, 1.4),
                        ("2025-04-21", 60, 1.6, 0.9, 2.3),
                    ]
                ],
            },
            "contributions": [
                dict(
                    Date=dates[0],
                    Base=80,
                    **{
                        "Leaf Activity": 36,
                        "Seed Activity": 36,
                        "Weather": -7,
                        "Overlap": -5,
                        "Model": 140,
                    },
                )
            ],
            "model_config": {
                "config": {"link": "log", "attribution": "removal_lift", "multiplier": 5},
                "control_references": {"Weather": {"resolved": "mean", "q_ref": 12}},
            },
            "posterior": [
                {
                    "variable": "Leaf Activity_alpha",
                    "mean": 0.42,
                    "sd": 0.12,
                    "hdi_3%": 0.19,
                    "hdi_97%": 0.63,
                    "r_hat": 1.003,
                }
            ],
        },
    }


def _museum():
    return {
        "model_hash": "synthetic-museum-v2",
        "results": {
            "channel_map": [
                {
                    "channel": "Posters",
                    "activity_column": "Poster Activity",
                    "spend_column": "Poster Spend",
                },
                {
                    "channel": "Audio guides",
                    "activity_column": "Audio Activity",
                    "spend_column": "Audio Spend",
                },
            ],
            "channel_summary": [
                {"Channel": "Poster Activity", "Sales": 90, "Revenue": 720, "Spend": 240, "ROI": 3},
                {"Channel": "Audio Activity", "Sales": 40, "Revenue": 320, "Spend": 160, "ROI": 2},
            ],
            "model_stats": [
                {"Test Name": "Max R_hat", "Output": "1.08", "Status": "warning"},
                {"Test Name": "R²", "Output": "0.91", "Status": "success"},
            ],
            "r_hat": [
                {"Parameter": "Poster Activity_alpha", "R_hat": 1.002},
                {"Parameter": "Poster Activity_decay", "R_hat": 1.08},
                {"Parameter": "Audio Activity_alpha", "R_hat": 1.004},
                {"Parameter": "sigma", "R_hat": 1.001},
            ],
            "posterior": [
                {"variable": "Poster Activity_alpha", "mean": 0.7, "r_hat": 1.002},
                {"variable": "Audio Activity_alpha", "mean": 0.4, "r_hat": 1.004},
            ],
            "decay_curves": {
                "Poster Activity": {
                    "adstock_type": "geometric",
                    "mean": 0.5,
                    "lower": 0.3,
                    "upper": 0.7,
                    "l_max": 4,
                    "curve": [1, 0.5, 0.25, 0.125],
                }
            },
            "model_config": {
                "config": {
                    "link": "identity",
                    "adstock_type": "geometric",
                    "saturation_type": "tanh",
                },
                "priors_resolved": [
                    {
                        "channel": "Posters",
                        "activity_column": "Poster Activity",
                        "overridden_fields": ["alpha_mean"],
                        "accepted_not_used": [
                            {"field": "theta_mean", "reason": "requires delayed adstock"}
                        ],
                    }
                ],
            },
            "long_run_rollup": {"available": False, "reason": "no_linked_var_model"},
            "cohort_ledger": {"available": False, "reason": "fitted_before_cohort_ledger"},
        },
    }


def acceptance_v2_tasks():
    """Return fresh fixture-owned tasks, without modifying shared fixtures."""
    garden, museum = _garden(), _museum()
    tasks = []

    def add(
        name,
        question,
        expected,
        sections,
        *,
        dataset="garden",
        alternatives=(),
        channel="Leaf Activity",
        window=None,
    ):
        tasks.append(
            ResultTask(
                id="acceptance_v2_" + name.replace("-", "_"),
                family=name,
                prompt=question + " Use only saved results. Do not fit or read predictions.",
                expected=expected,
                required_sections=frozenset(sections),
                fixture=deepcopy(garden if dataset == "garden" else museum),
                dataset="synthetic-" + dataset + "-v2",
                channel=channel,
                evidence_options=tuple(frozenset(x) for x in alternatives),
                evidence_window=window,
            )
        )

    add(
        "window-roi",
        "For synthetic-garden-v2, compare Leaf Activity and Seed Activity ROI from 14 to 21 April 2025 inclusive. Give each ROI, their positive difference and the higher channel, rounding ratios to six decimal places. Explain the aggregation basis.",
        {
            "leaf_roi": 1.75,
            "seed_roi": 1.857143,
            "roi_gap": 0.107143,
            "winner": "Seed Activity",
            "basis": "sum revenue divided by sum spend",
        },
        ["coefficients"],
        alternatives=(["coefficients"], ["channel_summary"]),
        window={"start": "2025-04-14", "end": "2025-04-21"},
        channel="",
    )
    add(
        "mean-median",
        "For synthetic-garden-v2 Leaflets, report headline marginal ROI mean and median, their difference and the current spend at which they are evaluated. Explain why swapping the two would misstate the requested statistic.",
        {"mean": 1.7, "median": 1.3, "difference": 0.4, "current_spend": 100},
        ["mroi_summary"],
    )
    add(
        "historical-marginal",
        "For synthetic-garden-v2 Leaflets on 14 April 2025, quote historical marginal ROI median, saved interval and spend. Explain whether this is the headline current-spend marginal ROI.",
        {
            "median": 0.8,
            "lower": 0.2,
            "upper": 1.4,
            "spend": 180,
            "interval_probability": 0.94,
            "evaluation_point": "historical_period_spend",
        },
        ["mroi_periods"],
    )
    add(
        "signed-reconciliation",
        "For synthetic-garden-v2 on 7 April 2025, reconcile the contribution components to Model and quantify the residual before Overlap. Explain whether negative Overlap is a media channel loss and how Weather's reference affects interpretation.",
        {
            "before_overlap": 145,
            "overlap": -5,
            "model": 140,
            "weather": -7,
            "weather_reference": "mean",
        },
        ["contributions", "model_config"],
    )
    add(
        "units-revenue",
        "For synthetic-garden-v2 Leaf Activity on 7 April 2025, quote its contribution in KPI units and revenue, and calculate revenue per KPI unit. Explain which saved section establishes revenue rather than treating the contribution as money.",
        {"contribution": 36, "revenue": 180, "revenue_per_unit": 5},
        ["contributions", "coefficients"],
        alternatives=(["contributions", "coefficients"], ["contributions", "channel_summary"]),
        window={"start": "2025-04-07", "end": "2025-04-07"},
    )
    add(
        "posterior-interval",
        "For synthetic-garden-v2 Leaf Activity_alpha, quote posterior mean, 94% HDI and interval width. State whether this quotes the saved posterior interval or independently reconstructs it from draws.",
        {"mean": 0.42, "lower": 0.19, "upper": 0.63, "width": 0.44, "interval_probability": 0.94},
        ["posterior"],
    )
    add(
        "diagnostic-attribution",
        "For synthetic-museum-v2, identify the exact parameter responsible for maximum R-hat, its value and its excess over 1.01. Explain whether the coefficient-only posterior table is sufficient to clear convergence.",
        {"parameter": "Poster Activity_decay", "r_hat": 1.08, "excess": 0.07},
        ["r_hat"],
        dataset="museum",
        channel="Poster Activity",
    )
    add(
        "decay-carryover",
        "For synthetic-museum-v2 Poster Activity, report the saved geometric decay mean and the lag-two retention implied by that mean. Explain why this is not a posterior interval for lag-two retention or a marginal ROI.",
        {"decay_mean": 0.5, "lag_two_retention": 0.25},
        ["decay_curves"],
        dataset="museum",
        channel="Poster Activity",
    )
    add(
        "inert-prior",
        "For synthetic-museum-v2 Posters, was theta_mean consumed by the fitted model? Identify the active adstock family and explain the saved reason. Also name the prior field recorded as taking effect.",
        {
            "consumed": False,
            "adstock_type": "geometric",
            "reason": "requires delayed adstock",
            "effective_field": "alpha_mean",
        },
        ["model_config"],
        dataset="museum",
        channel="Poster Activity",
    )
    add(
        "unavailable-longrun",
        "For synthetic-museum-v2, can you report a total long-run ROI from the saved long-run rollup? State its availability and exact reason, and explain why short-term ROI or the missing cohort ledger does not establish a zero long-run effect.",
        {"available": False, "reason": "no_linked_var_model"},
        ["long_run_rollup"],
        dataset="museum",
        channel="Poster Activity",
    )
    return tasks
