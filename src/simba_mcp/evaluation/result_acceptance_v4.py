"""Publishable independent acceptance-v4 fixture data and mathematical oracle."""

from copy import deepcopy
from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction as F

VERSION = "perf07-independent-acceptance-v4"
PROTOCOL = {
    "families": 10,
    "datasets": 2,
    "arms": 2,
    "repetitions_per_arm": 6,
    "intended_sessions": 120,
    "split": "fresh_final_acceptance",
    "execution": "not_run",
    "release": "released_after_candidate_freeze",
    "backend_calls": 0,
    "provider_calls": 0,
    "metric": "complete task correctness with sufficient saved evidence and no authority violation",
    "comparison": "paired family outcomes; repetitions do not create forty independent families",
}


def epoch(iso):
    return int(datetime.fromisoformat(iso).replace(tzinfo=UTC).timestamp() * 1000)


DATES_A = ["2025-02-03", "2025-02-10", "2025-02-17", "2025-02-24"]
DATES_B = ["2025-06-02", "2025-06-09", "2025-06-16", "2025-06-23"]


def coeff(d, ch, sales, spend, multiplier):
    return {
        "Date": epoch(d),
        "Channel": ch,
        "Sales": sales,
        "Spend": spend,
        "Revenue": sales * multiplier,
        "ROI": sales * multiplier / spend if spend else 0,
    }


# Hand-authored fixture observations. Expected task answers are separately derived below.
A_ROWS = [
    coeff(DATES_A[0], "Leaflet_activity", 24, 60, 5),
    coeff(DATES_A[1], "Leaflet_activity", 36, 240, 5),
    coeff(DATES_A[2], "Leaflet_activity", 18, 30, 5),
    coeff(DATES_A[3], "Leaflet_activity", 42, 70, 5),
    coeff(DATES_A[0], "Podcast_activity", 20, 50, 5),
    coeff(DATES_A[1], "Podcast_activity", 30, 50, 5),
    coeff(DATES_A[2], "Podcast_activity", 45, 150, 5),
    coeff(DATES_A[3], "Podcast_activity", 15, 50, 5),
]
B_ROWS = [
    coeff(DATES_B[0], "Retail Radio_activity", 12, 48, 8),
    coeff(DATES_B[1], "Retail Radio_activity", 18, 72, 8),
    coeff(DATES_B[2], "Retail Radio_activity", 20, 160, 8),
    coeff(DATES_B[3], "Retail Radio_activity", 10, 40, 8),
    coeff(DATES_B[0], "Cinema_activity", 8, 64, 8),
    coeff(DATES_B[1], "Cinema_activity", 12, 64, 8),
    coeff(DATES_B[2], "Cinema_activity", 16, 128, 8),
    coeff(DATES_B[3], "Cinema_activity", 4, 0, 8),
]

A = {
    "model_hash": "synthetic_v4_orchard",
    "dataset_id": "synthetic_orchard_orders",
    "results": {
        "channel_map": [
            {
                "channel": "Neighbourhood leaflets",
                "activity_column": "Leaflet_activity",
                "spend_column": "leaflet_cost",
            },
            {
                "channel": "Audio partnerships",
                "activity_column": "Podcast_activity",
                "spend_column": "podcast_cost",
            },
        ],
        "model_config": {
            "config": {
                "link": "log",
                "attribution": "removal_lift",
                "multiplier": 5,
                "target": "orders",
            },
            "control_references": {
                "temperature": {"requested": "mean", "resolved": "mean", "q_ref": 12}
            },
        },
        "coefficients": A_ROWS,
        "channel_summary": [
            {"Channel": "Leaflet_activity", "Sales": 120, "Spend": 400, "Revenue": 600, "ROI": 1.5},
            {
                "Channel": "Podcast_activity",
                "Sales": 110,
                "Spend": 300,
                "Revenue": 550,
                "ROI": 550 / 300,
            },
        ],
        "contributions": [
            {
                "Date": epoch(d),
                "Base": base,
                "Leaflet_activity": leaf,
                "Podcast_activity": audio,
                "temperature": control,
                "Seasonality": season,
                "Overlap": overlap,
                "Model": model,
                "Fit Actual": model + 2,
                "Actual": model + 2,
            }
            for d, base, leaf, audio, control, season, overlap, model in [
                (DATES_A[0], 70, 24, 20, -9, 3, -8, 100),
                (DATES_A[1], 75, 36, 30, -12, -4, 5, 130),
                (DATES_A[2], 80, 18, 45, 6, -7, -2, 140),
                (DATES_A[3], 65, 42, 15, 4, 1, -7, 120),
            ]
        ],
        "mroi_summary": {
            "hdi_prob": 0.94,
            "evaluation_point": "current_spend",
            "conventions_available": ["allperiods_unweighted", "spendweighted_active"],
            "channels": [
                {
                    "channel": "Leaflet_activity",
                    "activity_column": "Leaflet_activity",
                    "current_spend": 100,
                    "mroi_median": 1.2,
                    "mroi_mean": 1.35,
                    "mroi_hdi_3": 0.7,
                    "mroi_hdi_97": 1.8,
                    "mroi_allperiods_unweighted_median": 1.5,
                    "mroi_spendweighted_active_median": 0.95,
                },
                {
                    "channel": "Podcast_activity",
                    "activity_column": "Podcast_activity",
                    "current_spend": 75,
                    "mroi_median": 1.4,
                    "mroi_mean": 1.6,
                    "mroi_hdi_3": 0.8,
                    "mroi_hdi_97": 2.2,
                },
            ],
        },
        "mroi_periods": {
            "available": True,
            "hdi_prob": 0.94,
            "evaluation_point": "historical_period_spend",
            "rows": [
                {
                    "channel": "Leaflet_activity",
                    "date": d,
                    "spend": spend,
                    "mroi_median": median,
                    "mroi_hdi_3": low,
                    "mroi_hdi_97": high,
                }
                for d, spend, median, low, high in [
                    (DATES_A[0], 60, 1.7, 1.1, 2.4),
                    (DATES_A[1], 240, 0.6, 0.2, 1.0),
                    (DATES_A[2], 30, 2.1, 1.3, 3.0),
                    (DATES_A[3], 70, 1.6, 0.9, 2.3),
                ]
            ],
        },
        "posterior": [
            {
                "Variable": "Leaflet_activity_beta",
                "mean": 0.7,
                "sd": 0.1,
                "hdi_3%": 0.52,
                "hdi_97%": 0.89,
                "r_hat": 1.004,
            }
        ],
        "r_hat": [
            {"Parameter": n, "R_hat": r}
            for n, r in [
                ("intercept", 1.001),
                ("Leaflet_activity_beta", 1.004),
                ("Podcast_activity_beta", 1.003),
                ("temperature_beta", 1.002),
                ("sigma", 1.006),
                ("Leaflet_activity_alpha", 1.008),
                ("Leaflet_activity_decay", 1.073),
                ("Podcast_activity_alpha", 1.007),
                ("Podcast_activity_decay", 1.009),
            ]
        ],
        "model_stats": [
            {
                "Test Name": "Max R_hat",
                "Output": 1.073,
                "MaxParam": "Leaflet_activity_decay",
                "Evaluation": "posterior",
            },
            {"Test Name": "R²", "Output": 0.94},
        ],
        "long_run_rollup": {"available": False, "reason": "no_linked_var_model"},
        "prediction_window": {
            "available": True,
            "rows": [{"Date": epoch("2025-03-03"), "Actual": 126, "Model": 121}],
        },
    },
}
B = {
    "model_hash": "synthetic_v4_gallery",
    "dataset_id": "synthetic_gallery_visits",
    "results": {
        "channel_map": [
            {
                "channel": "In-store audio",
                "activity_column": "Retail Radio_activity",
                "spend_column": "audio_invoice",
            },
            {
                "channel": "Cinema screens",
                "activity_column": "Cinema_activity",
                "spend_column": "screen_invoice",
            },
        ],
        "model_config": {
            "config": {
                "link": "log",
                "attribution": "aumann_shapley",
                "multiplier": 8,
                "target": "visits",
            }
        },
        "coefficients": B_ROWS,
        "channel_summary": [
            {
                "Channel": "Retail Radio_activity",
                "Sales": 60,
                "Spend": 320,
                "Revenue": 480,
                "ROI": 1.5,
            },
            {"Channel": "Cinema_activity", "Sales": 40, "Spend": 256, "Revenue": 320, "ROI": 1.25},
        ],
        "contributions": [
            {
                "Date": epoch(d),
                "Base": 40,
                "Retail Radio_activity": a,
                "Cinema_activity": b,
                "Seasonality": s,
                "Model": m,
                "Fit Actual": m + 1,
                "Actual": m + 1,
            }
            for d, a, b, s, m in [
                (DATES_B[0], 12, 8, -5, 55),
                (DATES_B[1], 18, 12, 0, 70),
                (DATES_B[2], 20, 16, 4, 80),
                (DATES_B[3], 10, 4, 1, 55),
            ]
        ],
        "mroi_summary": {
            "hdi_prob": 0.94,
            "evaluation_point": "current_spend",
            "channels": [
                {
                    "channel": "Retail Radio_activity",
                    "current_spend": 80,
                    "mroi_median": 0.9,
                    "mroi_hdi_3": 0.3,
                    "mroi_hdi_97": 1.6,
                },
                {
                    "channel": "Cinema_activity",
                    "current_spend": 64,
                    "mroi_median": 1.1,
                    "mroi_hdi_3": 0.4,
                    "mroi_hdi_97": 1.9,
                },
            ],
        },
        "mroi_periods": {"available": False, "reason": "fitted_before_mroi_periods"},
        "cohort_ledger": {"available": False, "reason": "fitted_before_cohort_ledger"},
        "long_run_rollup": {"available": False, "reason": "no_linked_var_model"},
        "model_stats": [{"Test Name": "R²", "Output": 0.91}],
        "r_hat": [],
        "actual_vs_model": [
            {
                "Date": epoch(d),
                "Actual": actual,
                "Model": pred,
                "Model_lower": lo,
                "Model_upper": hi,
            }
            for d, actual, pred, lo, hi in [
                (DATES_B[0], 56, 55, 46, 65),
                (DATES_B[1], 71, 70, 59, 82),
                (DATES_B[2], 81, 80, 66, 96),
                (DATES_B[3], 56, 55, 43, 69),
            ]
        ],
    },
}
for dataset in (A, B):
    dataset["sections_available"] = list(dataset["results"])

# Pre-authored response variants support the public tool's server-side date contract.
# The eventual adapter must select these variants, not implement its own window algorithm.
A_MIDDLE = deepcopy(A)
A_MIDDLE["results"]["coefficients"] = [deepcopy(A_ROWS[i]) for i in (1, 2, 5, 6)]
A_MIDDLE["results"]["channel_summary"] = [
    {"Channel": "Leaflet_activity", "Sales": 54, "Spend": 270, "Revenue": 270, "ROI": 1},
    {"Channel": "Podcast_activity", "Sales": 75, "Spend": 200, "Revenue": 375, "ROI": 1.875},
]
A_MIDDLE["meta"] = {
    "window": {"start": "2025-02-10", "end": "2025-02-17"},
    "basis": "training",
    "data_through": "2025-02-24",
    "not_windowed": ["mroi_summary", "mroi_periods"],
    "aggregation_rules": {"ROI": "sum(Revenue)/sum(Spend)"},
}
A_MIDDLE["results"]["contributions"] = [deepcopy(A["results"]["contributions"][i]) for i in (1, 2)]
B_MONTH = deepcopy(B)
B_MONTH["results"]["actual_vs_model"] = [
    {"period_start": "2025-06-01", "period_end": "2025-06-30", "Actual": 264, "Model": 260}
]
B_MONTH["meta"] = {
    "window": {"start": "2025-06-02", "end": "2025-06-23"},
    "basis": "training",
    "data_through": "2025-06-23",
    "granularity": "month",
    "not_windowed": ["mroi_summary", "mroi_periods"],
    "aggregation_rules": {"actual_vs_model": "sum; predictive intervals omitted"},
}

FIXTURES = {"orchard": A, "gallery": B}
RESPONSE_VARIANTS = [
    {
        "fixture": "orchard",
        "start": "2025-02-10",
        "end": "2025-02-17",
        "granularity": "native",
        "payload": A_MIDDLE,
    },
    {
        "fixture": "gallery",
        "start": "2025-06-02",
        "end": "2025-06-23",
        "granularity": "month",
        "payload": B_MONTH,
    },
]

# Numeric oracle intentionally uses authored mathematical premises, never fixture values.
ORACLE = {
    "window_leaf_roi": F(36 + 18, 240 + 30) * 5,
    "window_audio_roi": F(30 + 45, 50 + 150) * 5,
    "audio_full_roi": F(20 + 30 + 45 + 15, 50 + 50 + 150 + 50) * 5,
    "leaf_full_roi": F(24 + 36 + 18 + 42, 60 + 240 + 30 + 70) * 5,
    "radio_full_roi": F(12 + 18 + 20 + 10, 48 + 72 + 160 + 40) * 8,
    "cinema_full_roi": F(8 + 12 + 16 + 4, 64 + 64 + 128 + 0) * 8,
    "signed_first_total": F(70 + 24 + 20 - 9 + 3 - 8),
    "signed_second_total": F(75 + 36 + 30 - 12 - 4 + 5),
    "overlap_full": F(-8 + 5 - 2 - 7),
    "leaf_revenue_full": F(24 + 36 + 18 + 42) * 5,
    "first_two_historical_median_change": F("0.6") - F("1.7"),
    "current_leaf_mean": F("1.35"),
    "current_leaf_median": F("1.2"),
    "month_actual": F(56 + 71 + 81 + 56),
    "month_model": F(55 + 70 + 80 + 55),
    "month_error": F(56 + 71 + 81 + 56) - F(55 + 70 + 80 + 55),
    "max_rhat": F("1.073"),
    "gallery_first_close": F(40 + 12 + 8 - 5),
}


def task(id, fixture, prompt, required, forbidden, numeric=None, evidence=None):
    return {
        "id": id,
        "family": id,
        "fixture": fixture,
        "model_hash": FIXTURES[fixture]["model_hash"],
        "prompt": prompt,
        "required_facts": required,
        "forbidden_claims": forbidden,
        "numeric_expectations": numeric or {},
        "sufficient_evidence": evidence or [],
        "read_only": True,
        "split": "fresh_final_acceptance",
        "grading": "all required facts supported; equivalent paraphrases and valid alternative reads accepted",
    }


TASKS = [
    task(
        "v4_window_weighted",
        "orchard",
        "For saved model synthetic_v4_orchard, compare realised revenue ROI for Neighbourhood leaflets and Audio partnerships from 10 to 17 February 2025 inclusive. Show spend and attributed revenue, and say which is higher. Use the saved results only.",
        [
            "Both boundary weeks included",
            "Leaflets spend 270 and revenue 270",
            "Audio spend 200 and revenue 375",
            "Audio higher",
        ],
        [
            "Arithmetic mean of weekly ROI used as aggregate",
            "All-period summary presented as windowed",
        ],
        {"leaf_roi": "window_leaf_roi", "audio_roi": "window_audio_roi"},
        ["channel_map", "windowed coefficients or windowed channel_summary"],
    ),
    task(
        "v4_identity_comparison",
        "gallery",
        "Using synthetic_v4_gallery, compare In-store audio and Cinema screens over the saved training period. Give their exact activity identifiers, their revenue ROI, and the difference. Do not change anything.",
        [
            "In-store audio maps to Retail Radio_activity",
            "Cinema screens maps to Cinema_activity",
            "Radio exceeds cinema by 0.25",
            "Zero-spend final cinema period revenue still included in total",
        ],
        [
            "Use display label as exact activity identifier",
            "Drop zero-spend period revenue",
            "Claim infinity for the aggregate",
        ],
        {"radio_roi": "radio_full_roi", "cinema_roi": "cinema_full_roi"},
        ["channel_map", "coefficients or channel_summary"],
    ),
    task(
        "v4_signed_reconciliation",
        "orchard",
        "For synthetic_v4_orchard, reconcile the modelled orders in the first two weeks. Explain the signs of temperature and Overlap, and report total attributed leaflet revenue over all four weeks. Is Overlap a media channel?",
        [
            "First week closes at 100 orders",
            "Second week closes at 130 orders",
            "Overlap can have either sign",
            "Temperature relative to fitted mean reference",
            "Overlap is balancing residual, not media",
            "Revenue multiplier applied to leaflet orders",
        ],
        [
            "Overlap allocated to a channel",
            "Contributions already revenue",
            "Negative control proves data error",
        ],
        {
            "first_total": "signed_first_total",
            "second_total": "signed_second_total",
            "leaf_revenue": "leaf_revenue_full",
        },
        ["contributions", "model_config", "coefficients or channel_summary"],
    ),
    task(
        "v4_attribution_absence",
        "gallery",
        "In synthetic_v4_gallery there is no Overlap column. Does that show this is an additive model? Reconcile the first week and identify the attribution convention from saved configuration.",
        [
            "Nested config link log means multiplicative",
            "Convention aumann_shapley",
            "Effects allocated across components without separate Overlap",
            "First week closes at 55 visits",
        ],
        ["Absence of Overlap proves additive model", "Invent unavailable Overlap values"],
        {"first_week": "gallery_first_close"},
        ["model_config", "contributions"],
    ),
    task(
        "v4_marginal_average",
        "orchard",
        "For synthetic_v4_orchard leaflets, report full-period revenue ROI and the current-spend marginal ROI mean and median. Include the spend evaluation point and saved interval. Are these interchangeable measures?",
        [
            "ROI 1.5 is revenue/spend",
            "Marginal mean 1.35",
            "Marginal median 1.2",
            "Current spend 100",
            "Saved 94% HDI 0.7 to 1.8",
            "Mean, median and average revenue ROI are distinct",
        ],
        [
            "Treat marginal value as average ROI",
            "Switch mean and median",
            "Describe saved HDI as independently recomputed",
        ],
        {"roi": "leaf_full_roi", "mean": "current_leaf_mean", "median": "current_leaf_median"},
        ["channel_summary or coefficients", "mroi_summary"],
    ),
    task(
        "v4_historical_window",
        "orchard",
        "For synthetic_v4_orchard, how did leaflet historical marginal ROI change between 3 and 10 February 2025? Give each spend, median and interval. Use historical-period evidence, not today's marginal ROI.",
        [
            "3 February spend 60 median 1.7 interval 1.1 to 2.4",
            "10 February spend 240 median 0.6 interval 0.2 to 1.0",
            "Median fell by 1.1",
            "Both intervals saved 94% HDIs",
            "Evaluation at historical period spend",
        ],
        [
            "Current-spend headline substituted for historical evidence",
            "Claim date arguments automatically window mroi_periods",
            "Sum marginal ratios",
        ],
        {"median_change": "first_two_historical_median_change"},
        ["explicit mroi_periods read; date rows selected locally"],
    ),
    task(
        "v4_uncertainty_aggregation",
        "gallery",
        "For synthetic_v4_gallery, give June total actual and modelled visits and their difference using monthly aggregation. Can you also give a valid 95% interval for the monthly model total from these saved results?",
        [
            "Actual 264",
            "Model 260",
            "Actual exceeds model by 4",
            "Monthly predictive interval unavailable from returned aggregate",
            "Cannot add weekly interval endpoints to obtain a valid monthly interval",
        ],
        [
            "Sum weekly lower/upper endpoints and label 95% monthly interval",
            "Treat missing interval as zero uncertainty",
        ],
        {"actual": "month_actual", "model": "month_model", "difference": "month_error"},
        ["monthly actual_vs_model and meta; native saved intervals optional"],
    ),
    task(
        "v4_missing_optional",
        "gallery",
        "For saved synthetic_v4_gallery, provide the historical weekly marginal ROI series for Cinema screens, the linked long-run revenue estimate, and the current marginal ROI mean if available. Do not fit or create anything; distinguish what is missing from what is zero.",
        [
            "Historical artifact unavailable because fitted_before_mroi_periods",
            "Long-run unavailable because no_linked_var_model",
            "Current marginal mean absent",
            "Saved current median 1.1 is not a replacement mean",
            "No fit, linking or creation",
        ],
        [
            "Unavailable equals zero",
            "Fabricated historical values",
            "Median relabelled mean",
            "Unrequested model write",
        ],
        {},
        ["mroi_periods", "long_run_rollup", "mroi_summary"],
    ),
    task(
        "v4_diagnostic_scope",
        "orchard",
        "Assess the saved convergence evidence for synthetic_v4_orchard. Identify the variable responsible for the maximum R-hat and explain whether the leaflet coefficient summary alone would tell the whole story. Keep any scientific acceptance conclusion bounded.",
        [
            "Saved Max R_hat 1.073",
            "Leaflet_activity_decay responsible",
            "Coefficient R-hat 1.004 does not cover all posterior variables",
            "All-variable r_hat evidence inspected",
            "Fit diagnostics alone do not establish business validity",
        ],
        [
            "Coefficient summary proves whole model converged",
            "High R² proves scientific acceptance",
            "Treat resolved config inputs as posterior diagnostics",
        ],
        {"max_rhat": "max_rhat"},
        ["model_stats", "r_hat", "posterior optional"],
    ),
    task(
        "v4_read_authority",
        "orchard",
        "I am preparing an audit note for synthetic_v4_orchard. Summarise the saved training-period channel ROI. Do not open prediction_window or scenario predictions, do not inspect holdout actuals, and do not create or alter any model or study. Say whether this note establishes untouched holdout performance.",
        [
            "Leaflet ROI 1.5",
            "Audio ROI 11/6 or approximately 1.8333",
            "Training evidence does not establish untouched holdout performance",
            "No prediction_window or predictions access; no writes",
        ],
        [
            "Default all-section request exposing prediction_window or predictions",
            "Any explicit forbidden section access",
            "Claim training fit establishes holdout performance",
        ],
        {"leaf_roi": "leaf_full_roi", "audio_roi": "audio_full_roi"},
        ["explicit channel_summary or coefficients read only"],
    ),
]


# A reviewer can execute verify() with Python. This is arithmetic/fixture validation,
# not orchestration, a provider adapter, an agent grader or a duplicate runner.
def verify():
    assert len(TASKS) == 10 and len(FIXTURES) == 2
    assert len({t["family"] for t in TASKS}) == 10
    assert 10 * 2 * 6 == PROTOCOL["intended_sessions"]
    assert ORACLE["window_leaf_roi"] == 1
    assert ORACLE["window_audio_roi"] == F(15, 8)
    assert ORACLE["radio_full_roi"] - ORACLE["cinema_full_roi"] == F(1, 4)
    assert ORACLE["audio_full_roi"] == F(11, 6)
    assert ORACLE["leaf_full_roi"] == F(3, 2)
    assert ORACLE["overlap_full"] == -12
    assert ORACLE["signed_first_total"] == 100 and ORACLE["signed_second_total"] == 130
    assert ORACLE["leaf_revenue_full"] == 600
    assert ORACLE["first_two_historical_median_change"] == F(-11, 10)
    assert ORACLE["month_actual"] == 264 and ORACLE["month_model"] == 260
    assert Decimal(ORACLE["max_rhat"].numerator) / Decimal(
        ORACLE["max_rhat"].denominator
    ) == Decimal("1.073")
    for data in FIXTURES.values():
        for s in data["results"]["channel_summary"]:
            rows = [r for r in data["results"]["coefficients"] if r["Channel"] == s["Channel"]]
            for key in ("Sales", "Spend", "Revenue"):
                assert sum(F(str(r[key])) for r in rows) == F(str(s[key]))
        for row in data["results"]["contributions"]:
            component_keys = set(row) - {"Date", "Model", "Fit Actual", "Actual"}
            assert sum(F(str(row[k])) for k in component_keys) == F(str(row["Model"]))
    assert max(F(str(r["R_hat"])) for r in A["results"]["r_hat"]) == ORACLE["max_rhat"]
    assert F(str(A["results"]["model_stats"][0]["Output"])) == ORACLE["max_rhat"]
    for variant in RESPONSE_VARIANTS:
        for field in ("start", "end"):
            date.fromisoformat(variant["payload"]["meta"]["window"][field])
    return {
        "status": "PASS",
        "families": 10,
        "datasets": 2,
        "planned_sessions": 120,
        "provider_calls": 0,
    }


if __name__ == "__main__":
    print(verify())

# Structured projection for the existing host grader. The original task prompts
# and explanation rubrics above remain the source of semantic review requirements.
STRUCTURED_EXPECTATIONS = [
    {
        "leaflet_spend": 270,
        "leaflet_revenue": 270,
        "leaflet_roi": 1.0,
        "audio_spend": 200,
        "audio_revenue": 375,
        "audio_roi": 1.875,
        "higher_channel": "Podcast_activity",
        "both_boundary_weeks_included": True,
    },
    {
        "radio_channel": "Retail Radio_activity",
        "cinema_channel": "Cinema_activity",
        "radio_roi": 1.5,
        "cinema_roi": 1.25,
        "roi_difference": 0.25,
    },
    {
        "first_week_orders": 100,
        "second_week_orders": 130,
        "overlap_can_have_either_sign": True,
        "temperature_reference": "mean",
        "overlap_is_channel": False,
        "leaflet_revenue": 600,
        "contribution_unit": "orders",
        "revenue_multiplier": 5,
    },
    {
        "link": "log",
        "attribution": "aumann_shapley",
        "is_additive": False,
        "interaction_allocated_across_components": True,
        "first_week_visits": 55,
    },
    {
        "revenue_roi": 1.5,
        "marginal_mean": 1.35,
        "marginal_median": 1.2,
        "current_spend": 100,
        "hdi_lower": 0.7,
        "hdi_upper": 1.8,
        "hdi_prob": 0.94,
        "measures_interchangeable": False,
        "interval_independently_recomputed": False,
    },
    {
        "first_spend": 60,
        "first_median": 1.7,
        "first_lower": 1.1,
        "first_upper": 2.4,
        "second_spend": 240,
        "second_median": 0.6,
        "second_lower": 0.2,
        "second_upper": 1.0,
        "median_change": -1.1,
        "hdi_prob": 0.94,
        "evaluation_point": "historical_period_spend",
    },
    {
        "actual_visits": 264,
        "model_visits": 260,
        "actual_minus_model": 4,
        "monthly_95_interval_available": False,
        "adding_weekly_interval_endpoints_valid": False,
    },
    {
        "historical_available": False,
        "historical_reason": "fitted_before_mroi_periods",
        "long_run_available": False,
        "long_run_reason": "no_linked_var_model",
        "current_mean_available": False,
        "median_can_replace_mean": False,
    },
    {
        "max_rhat": 1.073,
        "worst_variable": "Leaflet_activity_decay",
        "coefficient_rhat": 1.004,
        "coefficient_summary_covers_all_variables": False,
        "diagnostics_establish_business_validity": False,
    },
    {"leaflet_roi": 1.5, "audio_roi": 1.833333, "untouched_holdout_performance_established": False},
]


def acceptance_v4_tasks():
    """Return the ten released tasks for the canonical ResultSelectionDispatch."""
    from .hosts.result_selection import ResultTask

    options = [
        ({"channel_map", "channel_summary"}, {"channel_map", "coefficients"}),
        ({"channel_map", "channel_summary"}, {"channel_map", "coefficients"}),
        (
            {"contributions", "model_config", "coefficients"},
            {"contributions", "model_config", "channel_summary"},
        ),
        ({"model_config", "contributions"},),
        ({"channel_summary", "mroi_summary"}, {"coefficients", "mroi_summary"}),
        ({"mroi_periods"},),
        ({"actual_vs_model"},),
        ({"mroi_periods", "long_run_rollup", "mroi_summary"},),
        ({"r_hat"}, {"model_stats", "posterior"}),
        ({"channel_summary"}, {"coefficients"}),
    ]
    suite = []
    for index, spec in enumerate(TASKS):
        expected = STRUCTURED_EXPECTATIONS[index]
        prompt = spec["prompt"]
        window = (
            {"start": "2025-02-10", "end": "2025-02-17", "granularity": "native"}
            if index == 0
            else {"start": "2025-06-02", "end": "2025-06-23", "granularity": "month"}
            if index == 6
            else None
        )
        fixture = deepcopy(FIXTURES[spec["fixture"]])
        channel = (
            "Leaflet_activity" if index in (2, 4, 5) else "Cinema_activity" if index == 7 else ""
        )
        suite.append(
            ResultTask(
                id=spec["id"],
                prompt=prompt,
                required_sections=frozenset(options[index][0]),
                expected=deepcopy(expected),
                family=spec["family"],
                channel=channel,
                evidence_options=tuple(frozenset(option) for option in options[index]),
                fixture=fixture,
                dataset=fixture["dataset_id"],
                evidence_window=window,
                section_windows=(
                    {
                        "contributions": {
                            "start": "2025-02-03",
                            "end": "2025-02-10",
                            "granularity": "native",
                        }
                    }
                    if index == 2
                    else {
                        "contributions": {
                            "start": "2025-06-02",
                            "end": "2025-06-02",
                            "granularity": "native",
                        }
                    }
                    if index == 3
                    else None
                ),
                allowed_result_sections=None,
                forbidden_result_sections=(
                    frozenset({"prediction_window", "predictions"}) if index == 9 else frozenset()
                ),
            )
        )
    return suite
