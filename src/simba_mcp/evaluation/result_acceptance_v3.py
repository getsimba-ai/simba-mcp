"""Synthetic saved-result acceptance cases with independently authored answer rubrics."""

from copy import deepcopy
from datetime import UTC, datetime
from fractions import Fraction as F


def epoch(date):
    return int(datetime.fromisoformat(date).replace(tzinfo=UTC).timestamp() * 1000)


def dataset(name, dates, series):
    rows = []
    summaries = []
    for channel, values in series.items():
        for date, (spend, revenue, sales) in zip(dates, values, strict=True):
            rows.append(
                {
                    "Date": epoch(date),
                    "Channel": channel,
                    "Spend": spend,
                    "Revenue": revenue,
                    "Sales": sales,
                    "ROI": revenue / spend if spend else 0,
                }
            )
        spend = sum(v[0] for v in values)
        revenue = sum(v[1] for v in values)
        summaries.append(
            {
                "Channel": channel,
                "Spend": spend,
                "Revenue": revenue,
                "Sales": sum(v[2] for v in values),
                "ROI": revenue / spend if spend else 0,
            }
        )
    return {
        "model_hash": name,
        "results": {
            "coefficients": rows,
            "channel_summary": summaries,
            "channel_map": [
                {
                    "channel": c.replace("_activity", "").title(),
                    "activity_column": c,
                    "spend_column": c.replace("_activity", "_spend"),
                }
                for c in series
            ],
        },
    }


A = dataset(
    "synthetic_estuary_v3",
    ["2025-02-03", "2025-02-10", "2025-02-17"],
    {
        "radio_activity": [(80, 280, 40), (320, 480, 60), (200, 440, 55)],
        "cinema_activity": [(120, 180, 30), (180, 450, 75), (300, 600, 100)],
    },
)
B = dataset(
    "synthetic_orchard_v3",
    ["2025-05-05", "2025-05-12", "2025-05-19"],
    {
        "print_activity": [(90, 270, 45), (210, 315, 45), (300, 660, 110)],
        "audio_activity": [(200, 500, 100), (100, 150, 25), (150, 450, 75)],
    },
)
A["results"].update(
    {
        "model_config": {"config": {"link": "log", "attribution": "removal_lift"}},
        "contributions": [
            dict(
                Date=epoch("2025-02-03"),
                radio_activity=40,
                cinema_activity=30,
                Base=100,
                Seasonality=12,
                **{
                    "Event Effect": -7,
                    "Overlap": -15,
                    "Model": 160,
                    "Fit Actual": 162,
                    "Actual": 162,
                },
            )
        ],
        "mroi_summary": {
            "channels": [
                {
                    "channel": "radio_activity",
                    "current_spend": 200,
                    "mroi_mean": 1.75,
                    "mroi_median": 1.6,
                    "mroi_hdi_3": 0.7,
                    "mroi_hdi_97": 2.8,
                }
            ]
        },
        "mroi_periods": {
            "available": True,
            "hdi_prob": 0.94,
            "evaluation_point": "historical_period_spend",
            "rows": [
                {
                    "channel": "radio_activity",
                    "date": "2025-02-03",
                    "spend": 80,
                    "mroi_median": 2.6,
                    "mroi_hdi_3": 1.1,
                    "mroi_hdi_97": 3.8,
                },
                {
                    "channel": "radio_activity",
                    "date": "2025-02-10",
                    "spend": 320,
                    "mroi_median": 0.9,
                    "mroi_hdi_3": 0.2,
                    "mroi_hdi_97": 1.7,
                },
                {
                    "channel": "radio_activity",
                    "date": "2025-02-17",
                    "spend": 200,
                    "mroi_median": 1.4,
                    "mroi_hdi_3": 0.5,
                    "mroi_hdi_97": 2.4,
                },
            ],
        },
        "long_run_rollup": {"available": False, "reason": "no_linked_var_model"},
    }
)
B["results"].update(
    {
        "model_config": {"config": {"link": "log", "attribution": "aumann_shapley"}},
        "contributions": [
            dict(
                Date=epoch("2025-05-05"),
                print_activity=45,
                audio_activity=100,
                Base=120,
                Seasonality=-10,
                **{"Event Effect": 5, "Model": 260, "Fit Actual": 258, "Actual": 258},
            )
        ],
        "mroi_summary": {
            "channels": [
                {
                    "channel": "print_activity",
                    "current_spend": 200,
                    "mroi_median": 1.3,
                    "mroi_hdi_3": 0.4,
                    "mroi_hdi_97": 2.1,
                }
            ]
        },
        "mroi_periods": {"available": False, "reason": "fitted_before_mroi_periods"},
        "long_run_rollup": {"available": False, "reason": "no_linked_var_model"},
        "model_stats": [
            {
                "Evaluation": "posterior",
                "MaxParam": "print_activity_decay",
                "Median": 1.003,
                "Output": 1.061,
                "Status": "review",
                "Test Name": "Max R_hat",
            }
        ],
        "r_hat": [
            {"Parameter": "print_activity", "R_hat": 1.002},
            {"Parameter": "print_activity_decay", "R_hat": 1.061},
            {"Parameter": "audio_activity", "R_hat": 1.003},
            {"Parameter": "audio_activity_decay", "R_hat": 1.008},
        ],
    }
)

DATASETS = {"estuary": A, "orchard": B}
SPECS = []
RUBRICS = {}


def case(
    cid,
    family,
    data,
    question,
    sections,
    expected,
    *,
    channel="",
    window=None,
    alternatives=(),
    allowed_sections=None,
):
    fixture = DATASETS[data]
    RUBRICS[cid] = {k: v for k, v in expected.items() if k != "facts"}
    SPECS.append(
        {
            "id": cid,
            "family": family,
            "dataset": data,
            "prompt": f"For saved model {fixture['model_hash']}: {question} Use saved evidence only. Do not refit or change the model. Include the requested explanation in your answer.",
            "required_sections": frozenset(sections),
            "expected": expected["facts"],
            "fixture": fixture,
            "channel": channel,
            "evidence_window": window,
            "evidence_options": tuple(frozenset(s) for s in alternatives),
            "allowed_result_sections": frozenset(allowed_sections) if allowed_sections else None,
        }
    )


case(
    "v3_window_aggregate",
    "window_aggregate",
    "estuary",
    "For 3 to 10 February 2025 inclusive, give radio_activity total spend, revenue and aggregate ROI. Explain why the simple average of its period ROI values is inappropriate.",
    ["coefficients"],
    {
        "facts": {"spend": 400, "revenue": 760, "roi": 1.9},
        "explanation": [
            "Sum period revenue and spend before dividing; an arithmetic mean weights unequal-spend periods equally."
        ],
        "reject": ["ROI is 2.5"],
    },
    channel="radio_activity",
    window={"start": "2025-02-03", "end": "2025-02-10"},
    alternatives=(("coefficients",), ("channel_summary",)),
)
case(
    "v3_channel_comparison",
    "channel_comparison",
    "orchard",
    "Across all three saved periods, compare print_activity and audio_activity aggregate ROI and give the absolute gap. Does this historical comparison establish which channel would yield more from the next pound?",
    ["channel_summary"],
    {
        "facts": {"print_roi": 2.075, "audio_roi": 22 / 9, "gap": 133 / 360},
        "explanation": [
            "Audio has higher historical aggregate ROI. Historical average ROI alone does not establish marginal return on the next pound."
        ],
        "reject": ["Historical winner must receive the next pound"],
    },
    alternatives=(("channel_summary",), ("coefficients",)),
)
case(
    "v3_signed_reconciliation",
    "signed_reconciliation",
    "estuary",
    "For 3 February 2025, reconcile Model from Base, both media channels, Seasonality, Event Effect and Overlap. Give the subtotal before Overlap and the final total. Explain whether the negative Overlap is another media channel.",
    ["contributions", "channel_map"],
    {
        "facts": {"subtotal": 175, "overlap": -15, "model": 160},
        "explanation": [
            "Overlap is a signed balancing residual, not a media channel. All values are KPI units."
        ],
        "reject": ["Rank Overlap as media"],
    },
    window={"start": "2025-02-03", "end": "2025-02-03"},
    alternatives=(("contributions",), ("contributions", "verified_media_identity")),
)
case(
    "v3_no_overlap_attribution",
    "no_overlap_attribution",
    "orchard",
    "For 5 May 2025, reconcile the contribution total and explain why no Overlap column is needed in this saved model. State its saved link and attribution convention.",
    ["contributions", "model_config"],
    {
        "facts": {"model": 260, "link": "log", "attribution": "aumann_shapley"},
        "explanation": [
            "Allocated components close to Model without Overlap under the saved Aumann-Shapley attribution. Absence of Overlap does not show an additive model."
        ],
    },
    window={"start": "2025-05-05", "end": "2025-05-05"},
)
case(
    "v3_headline_estimands",
    "headline_estimands",
    "estuary",
    "Report radio_activity saved headline mROI mean and median, the current spend evaluation point, and the saved 94% HDI. Can the reported interval be described as independently recomputed from posterior draws?",
    ["mroi_summary"],
    {
        "facts": {"mean": 1.75, "median": 1.6, "current_spend": 200, "lower": 0.7, "upper": 2.8},
        "explanation": [
            "Mean and median are distinct summaries. The interval is quoted from the saved artefact, not independently recomputed from draws."
        ],
    },
    channel="radio_activity",
)
case(
    "v3_historical_mroi_scope",
    "historical_mroi_scope",
    "estuary",
    "For radio_activity on 10 February 2025 only, report historical-period mROI median, saved 94% HDI and spend. Explain its evaluation point and why a date filter must not cause you to sum the full mROI series.",
    ["mroi_periods"],
    {
        "facts": {"median": 0.9, "lower": 0.2, "upper": 1.7, "spend": 320},
        "explanation": [
            "Evaluation is at historical period spend. mroi_periods is returned as fitted and is not window-aggregated; select the requested dated row, do not sum marginal ratios."
        ],
    },
    channel="radio_activity",
    window={"start": "2025-02-10", "end": "2025-02-10"},
)
case(
    "v3_optional_history_absent",
    "optional_history_absent",
    "orchard",
    "Can you report print_activity historical-period mROI for 12 May 2025 from the saved artefact? Explain any limitation and whether the headline current-spend mROI is a valid substitute.",
    ["mroi_periods"],
    {
        "facts": {"available": False, "reason": "fitted_before_mroi_periods"},
        "explanation": [
            "Historical-period artefact is unavailable because the fit predates it. Current-spend headline mROI does not establish the requested historical value. A refit could enable the artefact but is not authorised here."
        ],
    },
    channel="print_activity",
    window={"start": "2025-05-12", "end": "2025-05-12"},
)
case(
    "v3_kpi_revenue_basis",
    "kpi_revenue_basis",
    "estuary",
    "For radio_activity on 3 and 10 February 2025, give summed Sales and Revenue and the implied Revenue/Sales factor for each date. Would one constant factor reproduce both saved period revenues?",
    ["coefficients"],
    {
        "facts": {"sales": 100, "revenue": 760, "first_factor": 7, "second_factor": 8},
        "explanation": [
            "The period factors differ, so one constant factor cannot reproduce both rows. Contributions are KPI units and are not revenue already."
        ],
    },
    channel="radio_activity",
    window={"start": "2025-02-03", "end": "2025-02-10"},
    alternatives=(("coefficients",), ("period_revenue_rows",)),
)
case(
    "v3_diagnostic_parameter_scope",
    "diagnostic_parameter_scope",
    "orchard",
    "Report saved Max R_hat, identify the parameter attaining it, and count parameters with R_hat strictly above 1.01. Does the media coefficient subset alone support a claim that every posterior variable is at most 1.01? Explain what these saved diagnostics establish, without declaring business validity or treating R_hat alone as proof of convergence.",
    ["model_stats", "r_hat"],
    {
        "facts": {
            "max_r_hat": 1.061,
            "max_parameter": "print_activity_decay",
            "above_threshold_count": 1,
        },
        "explanation": [
            "The transform decay parameter exceeds the requested threshold even though media coefficient rows do not. All-variable R_hat evidence is needed to assess this threshold claim. These are saved diagnostics, not independent convergence proof or business validity."
        ],
        "reject": [
            "Every posterior variable is at most 1.01",
            "Good coefficient rows prove convergence",
        ],
    },
    alternatives=(("model_stats", "r_hat"), ("r_hat",)),
)
case(
    "v3_prediction_access_boundary",
    "prediction_access_boundary",
    "orchard",
    "Using only channel_summary, give total historical media spend and revenue across the two channels. Do not access prediction_window. Explain whether these aggregate historical totals certify untouched holdout performance.",
    ["channel_summary"],
    {
        "facts": {"spend": 1050, "revenue": 2345},
        "explanation": [
            "Historical aggregates do not certify untouched holdout performance. prediction_window must not be accessed."
        ],
        "forbidden_sections": ["prediction_window"],
    },
    allowed_sections=("channel_summary",),
)


def acceptance_v3_tasks():
    from simba_mcp.evaluation.hosts.result_selection import ResultTask

    specs = deepcopy(SPECS)
    for spec in specs:
        if spec["id"] == "v3_kpi_revenue_basis":
            # Prospective validation clarification only. Preserve the original
            # ambiguous prompt and every historical score in frozen reports.
            spec["paraphrase"] = spec["prompt"].replace(
                "give summed Sales and Revenue and the implied Revenue/Sales factor for each date",
                "give combined Sales and combined Revenue across both dates, plus the implied "
                "Revenue/Sales factor separately for each date",
            )
    return tuple(ResultTask(**spec) for spec in specs)


def independent_oracles():
    """Manual source quantities, independently expressed with exact rationals."""
    return {
        "v3_window_aggregate": {"spend": F(80) + 320, "revenue": F(280) + 480, "roi": F(760, 400)},
        "v3_channel_comparison": {
            "print_roi": F(1245, 600),
            "audio_roi": F(1100, 450),
            "gap": F(1100, 450) - F(1245, 600),
        },
        "v3_signed_reconciliation": {
            "subtotal": F(100) + 40 + 30 + 12 - 7,
            "overlap": F(-15),
            "model": F(175) - 15,
        },
        "v3_no_overlap_attribution": {"model": F(120) + 45 + 100 - 10 + 5},
        "v3_headline_estimands": {
            "mean": F(7, 4),
            "median": F(8, 5),
            "current_spend": F(200),
            "lower": F(7, 10),
            "upper": F(14, 5),
        },
        "v3_historical_mroi_scope": {
            "median": F(9, 10),
            "lower": F(1, 5),
            "upper": F(17, 10),
            "spend": F(320),
        },
        "v3_kpi_revenue_basis": {
            "sales": F(40) + 60,
            "revenue": F(280) + 480,
            "first_factor": F(280, 40),
            "second_factor": F(480, 60),
        },
        "v3_diagnostic_parameter_scope": {
            "max_r_hat": max(F(1002, 1000), F(1061, 1000), F(1003, 1000), F(1008, 1000)),
            "above_threshold_count": sum(
                v > F(101, 100)
                for v in (F(1002, 1000), F(1061, 1000), F(1003, 1000), F(1008, 1000))
            ),
        },
        "v3_prediction_access_boundary": {
            "spend": F(90) + 210 + 300 + 200 + 100 + 150,
            "revenue": F(270) + 315 + 660 + 500 + 150 + 450,
        },
    }
