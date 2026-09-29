"""Fresh synthetic acceptance packet, independent of provider answers and tuning.

Authored case specifications were reviewed against public contracts. This packet
tests evidence use, not scientific validity, live audit persistence or population
effectiveness. Expected answers must never enter guidance selection or tuning.
"""

from copy import deepcopy
from datetime import UTC, datetime

from .hosts.result_selection import ResultTask

ACCEPTANCE_VERSION = 1
WINDOW = {"start": "2026-03-10", "end": "2026-03-24", "granularity": "native"}
PERIOD_INPUTS = (
    ("2026-03-03", ((900, 100), (800, 100), (700, 100))),
    ("2026-03-10", ((30, 10), (72, 24), (15, 5))),
    ("2026-03-17", ((110, 50), (20, 20), (28, 7))),
    ("2026-03-24", ((60, 20), (90, 30), (35, 14))),
    ("2026-03-31", ((600, 100), (500, 100), (400, 100))),
)


def _fixture():
    names = ("Audio", "Cinema", "Affiliate")
    coefficients = [
        {
            "Date": int(datetime.fromisoformat(date).replace(tzinfo=UTC).timestamp() * 1000),
            "Channel": name + "_activity",
            "Revenue": revenue,
            "Spend": spend,
            "Sales": revenue / 4,
            "ROI": revenue / spend,
        }
        for date, values in PERIOD_INPUTS
        for name, (revenue, spend) in zip(names, values, strict=True)
    ]
    rows = {
        "coefficients": coefficients,
        "channel_summary": [
            {
                "Channel": name + "_activity",
                "Revenue": revenue,
                "Spend": spend,
                "Sales": revenue / 4,
                "ROI": revenue / spend,
            }
            for name, revenue, spend in (
                ("Audio", 1700, 280),
                ("Cinema", 1482, 274),
                ("Affiliate", 1178, 226),
            )
        ],
        "channel_map": [
            {
                "channel": name,
                "activity_column": name + "_activity",
                "spend_column": name.lower() + "_spend",
            }
            for name in names
        ],
        "mroi_summary": {
            "hdi_prob": 0.94,
            "evaluation_point": "current_spend",
            "spend_convention": "mean_active_period",
            "conventions_available": ["allperiods_unweighted", "spendweighted_active"],
            "channels": [
                {
                    "channel": "Audio",
                    "activity_column": "Audio_activity",
                    "current_spend": 56,
                    "mroi_mean": 1.80,
                    "mroi_median": 1.45,
                    "mroi_hdi_3": 0.40,
                    "mroi_hdi_97": 3.10,
                    "mroi_allperiods_unweighted_median": 0.95,
                    "mroi_spendweighted_active_median": 1.20,
                }
            ],
        },
        "model_stats": [{"Test Name": "Max R_hat", "Output": "1.07", "Status": "warning"}],
        "r_hat": [
            {"Parameter": p, "R_hat": r}
            for p, r in (("Audio_decay", 1.07), ("Cinema_beta", 1.002), ("Affiliate_beta", 1.004))
        ],
        "contributions": [
            {
                "Date": coefficients[0]["Date"],
                "Base": 100,
                "Audio_activity": 225,
                "Cinema_activity": 200,
                "Affiliate_activity": 175,
                "Weather": -8,
                "Seasonality": 5,
                "Overlap": 3,
                "Model": 700,
            }
        ],
        "model_config": {"config": {"link": "log", "attribution": "removal_lift"}},
        "response_curves": [{"Spend": i, "Audio_activity": i * 1.8} for i in range(100)],
    }
    return {
        "model_hash": "result-example",
        "status": "complete",
        "model_type": "mmm",
        "results": rows,
        "sections_available": list(rows),
    }


def acceptance_tasks():
    """Ten reviewed specifications using the existing dispatcher and provider runner.

    Case E preserves the public contract's 94% probability, rather than inventing
    arbitrary interval support. F supplies reference/multiplier context in the
    question: no unverified backend nesting is fabricated. J permits recovery but
    never requires an agent to make an avoidable broad call.
    """
    prefix = (
        "The completed saved model is result-example. All data are synthetic. "
        "Revenue and spend are GBP. Read saved evidence only; do not fit anything. "
    )

    def task(letter, question, required, expected, **kwargs):
        return ResultTask(
            id=f"acceptance_{letter}",
            prompt=prefix + question,
            required_sections=frozenset(required),
            expected=expected,
            family=f"acceptance_{letter}",
            channel="",
            dataset="independent_specifications_v1",
            fixture=kwargs.pop("fixture", _fixture()),
            **kwargs,
        )

    zero = _fixture()
    zero["results"]["channel_summary"] = [
        {"Channel": "Dormant Radio", "Revenue": 45, "Spend": 0, "Sales": 11.25, "ROI": 0.0}
    ]
    zero["results"]["coefficients"] = [
        {**zero["results"]["channel_summary"][0], "Date": 1773100800000}
    ]
    zero["results"]["channel_map"] = [
        {
            "channel": "Dormant Radio",
            "activity_column": "Dormant Radio",
            "spend_column": "radio_spend",
        }
    ]
    missing = _fixture()
    for section in ("model_stats", "r_hat"):
        missing["results"].pop(section)
    missing["sections_available"] = list(missing["results"])
    collision = _fixture()
    collision["results"]["channel_map"] = [
        {"channel": "Audio A", "activity_column": "Audio_activity", "spend_column": "a_spend"},
        {"channel": "Audio B", "activity_column": "Audio_spend", "spend_column": "b_spend"},
    ]
    collision["results"]["channel_summary"] = [
        {
            "Channel": name,
            "Revenue": revenue,
            "Spend": spend,
            "Sales": revenue / 4,
            "ROI": revenue / spend,
        }
        for name, revenue, spend in (("Audio_activity", 84, 28), ("Audio_spend", 90, 45))
    ]
    collision["results"]["coefficients"] = [
        {**row, "Date": 1773100800000} for row in collision["results"]["channel_summary"]
    ]
    recovery = _fixture()
    recovery["results"]["mroi_summary"]["channels"][0].update(
        mroi_median=1.25, mroi_hdi_3=0.60, mroi_hdi_97=2.30
    )
    marginal = _fixture()
    marginal["results"]["mroi_summary"]["channels"][0]["current_spend"] = 80
    decomposition = _fixture()
    decomposition["results"]["contributions"][0].update(
        Audio_activity=18, Cinema_activity=12, Model=130
    )
    decomposition["results"]["contributions"][0].pop("Affiliate_activity")
    # Different questions describe different synthetic saved models. Restrict
    # unrelated sections when specialised inputs replace their source rows.
    for fixture, sections in (
        (zero, {"channel_summary", "coefficients", "channel_map"}),
        (collision, {"channel_summary", "coefficients", "channel_map"}),
        (marginal, {"mroi_summary", "channel_map"}),
        (decomposition, {"contributions", "model_config"}),
    ):
        fixture["results"] = {k: v for k, v in fixture["results"].items() if k in sections}
        fixture["sections_available"] = list(fixture["results"])
    return [
        task(
            "a",
            "For 10 to 24 March 2026 inclusive, give total revenue, spend and ROI "
            "across Audio, Cinema and Affiliate. Round ROI to six places. Return JSON fields "
            "revenue, spend, roi, currency, and explain the calculation.",
            {"channel_summary"},
            {"revenue": 460, "spend": 180, "roi": 2.555556, "currency": "GBP"},
            evidence_window=WINDOW,
            evidence_options=(frozenset({"channel_summary"}), frozenset({"coefficients"})),
        ),
        task(
            "b",
            "Explain Dormant Radio's saved ROI. The supplied window contract represents "
            "ROI as zero when spend is zero. Is the revenue/spend ratio finite and defined, "
            "and does this establish an investment ranking? Return JSON fields saved_roi, "
            "finite_ratio_defined, investment_ranking_established and explain.",
            {"channel_summary"},
            {
                "saved_roi": 0,
                "finite_ratio_defined": False,
                "investment_ranking_established": False,
            },
            fixture=zero,
        ),
        task(
            "c",
            "Does completion meet our declared maximum R-hat gate of at most 1.01, "
            "and which parameter breaches it? Return JSON fields gate_passed, max_r_hat, "
            "breaching_parameter and explain the limits of this conclusion.",
            {"r_hat"},
            {"gate_passed": False, "max_r_hat": 1.07, "breaching_parameter": "Audio_decay"},
        ),
        task(
            "d",
            "Can saved model_stats and r_hat establish convergence? Request both. "
            "Return JSON fields convergence and reason; explain only what the response establishes.",
            {"model_stats", "r_hat"},
            {"convergence": "unknown", "reason": "not_returned"},
            fixture=missing,
        ),
        task(
            "e",
            "Give Audio's headline marginal ROI mean at current spend and saved interval. "
            "Return JSON fields mean, lower, upper, hdi_prob, current_spend, historical_average "
            "and explain whether this is either saved historical averaging convention.",
            {"mroi_summary"},
            {
                "mean": 1.8,
                "lower": 0.4,
                "upper": 3.1,
                "hdi_prob": 0.94,
                "current_spend": 80,
                "historical_average": False,
            },
            fixture=marginal,
        ),
        task(
            "f",
            "Reconcile the decomposition row in KPI units. Supplied saved context: "
            "Weather uses its average reference and revenue multiplier is 4. Return JSON "
            "fields component_sum, model, overlap_is_channel, weather_reference; explain "
            "Overlap and the negative Weather contribution without inferring raw weather values.",
            {"contributions", "model_config"},
            {
                "component_sum": 130,
                "model": 130,
                "overlap_is_channel": False,
                "weather_reference": "average",
            },
            fixture=decomposition,
        ),
        task(
            "g",
            "Give the result for 'Audio' only if its identity is unique. The request "
            "uses a normalised alias stripping activity/spend suffixes. Inspect the canonical "
            "map. Return JSON fields ambiguous and identifiers (sorted exact activity identifiers); "
            "explain what is needed before giving a single-channel result.",
            {"channel_map"},
            {"ambiguous": True, "identifiers": ["Audio_activity", "Audio_spend"]},
            fixture=collision,
        ),
        task(
            "h",
            "Can you report historical marginal ROI from this saved model? Explicitly "
            "check mroi_periods, return JSON fields available and reason, and explain the scope "
            "of any unavailable artefact. Do not fit anything.",
            {"mroi_periods"},
            {"available": False, "reason": "fitted_before_mroi_periods"},
        ),
        task(
            "i",
            "Report total saved training-period revenue only, across all configured "
            "channels. Do not access prediction-window data. Return JSON fields revenue and "
            "currency. Do not infer untouched holdout status.",
            {"channel_summary"},
            {"revenue": 4360, "currency": "GBP"},
        ),
        task(
            "j",
            "Give Audio's saved headline mROI median and interval. This synthetic "
            "session has a 2500-byte results response ceiling; an oversized request returns "
            "an error with no partial evidence. Use existing evidence and recover selectively "
            "if needed. Return JSON fields median, lower, upper, hdi_prob.",
            {"mroi_summary"},
            {"median": 1.25, "lower": 0.6, "upper": 2.3, "hdi_prob": 0.94},
            fixture=deepcopy(recovery),
            max_response_bytes=2500,
            allow_recovery_errors=True,
        ),
    ]
