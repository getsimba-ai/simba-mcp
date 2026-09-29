"""Fresh synthetic acceptance tasks, independently authored after development schema exposure.

Saved-result contracts and arithmetic only; these cases cannot establish scientific
MMM validity. Labels are fixed before provider execution and contain no real data.
"""

from copy import deepcopy
from datetime import UTC, datetime

from .hosts.result_selection import ResultTask

FRESH_ACCEPTANCE_VERSION = 1


def _date(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp() * 1000)


def _fixture(dataset):
    if dataset == "harbour":
        channels = [
            ("Audio", "Audio_activity", "audio_cost"),
            ("Cinema", "Cinema_activity", "cinema_cost"),
        ]
        observations = [
            ("2026-03-02", "Audio_activity", 90, 30),
            ("2026-03-09", "Audio_activity", 60, 15),
            ("2026-03-16", "Audio_activity", 42, 21),
            ("2026-03-02", "Cinema_activity", 40, 20),
            ("2026-03-09", "Cinema_activity", 0, 0),
            ("2026-03-16", "Cinema_activity", 36, 12),
        ]
        extra = {
            "model_stats": [{"Test Name": "Max R_hat", "Output": "1.008", "Status": "success"}],
            "r_hat": [
                {"Parameter": "audio_beta", "R_hat": 1.008},
                {"Parameter": "cinema_beta", "R_hat": 1.004},
            ],
            "contributions": [
                {
                    "Date": _date("2026-03-09"),
                    "Audio_activity": 10,
                    "Cinema_activity": 0,
                    "Base": 55,
                    "holiday": -7,
                    "Overlap": 3,
                    "Model": 61,
                }
            ],
            "model_config": {"config": {"link": "log", "attribution": "removal_lift"}},
            "mroi_summary": {
                "hdi_prob": 0.94,
                "evaluation_point": "current_spend",
                "spend_convention": "mean_active_period",
                "channels": [
                    {
                        "channel": "Audio",
                        "activity_column": "Audio_activity",
                        "current_spend": 22,
                        "mroi_median": 0.8,
                        "mroi_hdi_3": -0.2,
                        "mroi_hdi_97": 1.7,
                    }
                ],
            },
            "response_curves": [
                {"Spend": x, "Audio_activity": y}
                for x, y in [(0, 0), (10, 14), (20, 22), (30, 27), (40, 30)]
            ],
        }
    else:
        channels = [
            ("Outdoor panel", "Outdoor Activity", "panel_cost"),
            ("Outdoor digital", "outdoor_activity", "digital_cost"),
            ("Partnership", "Partnership_activity", "partner_cost"),
        ]
        observations = [
            ("2026-06-05", "Outdoor Activity", 96, 24),
            ("2026-06-19", "Outdoor Activity", 54, 18),
            ("2026-06-05", "outdoor_activity", 35, 7),
            ("2026-06-19", "outdoor_activity", 28, 14),
            ("2026-06-05", "Partnership_activity", 15, 0),
            ("2026-06-19", "Partnership_activity", 9, 0),
        ]
        extra = {"model_config": {"config": {"link": "identity", "attribution": "additive"}}}
    rows = [
        {
            "Date": _date(d),
            "Channel": c,
            "Revenue": r,
            "Spend": s,
            "Sales": r / 6,
            "ROI": r / s if s else 0.0,
        }
        for d, c, r, s in observations
    ]
    summaries = []
    for _, activity, _ in channels:
        matching = [r for r in rows if r["Channel"] == activity]
        revenue, spend = sum(r["Revenue"] for r in matching), sum(r["Spend"] for r in matching)
        summaries.append(
            {
                "Channel": activity,
                "Revenue": revenue,
                "Spend": spend,
                "Sales": revenue / 6,
                "ROI": revenue / spend if spend else 0.0,
            }
        )
    results = {
        "channel_map": [
            {"channel": c, "activity_column": a, "spend_column": s} for c, a, s in channels
        ],
        "coefficients": rows,
        "channel_summary": summaries,
        **extra,
    }
    return {
        "model_hash": "result-example",
        "status": "complete",
        "model_type": "mmm",
        "sections_available": list(results),
        "results": results,
    }


def fresh_acceptance_tasks():
    """Return eight fresh cases across eight families and two synthetic datasets."""
    common = "Read only saved results for model result-example. All values are synthetic. Revenue and spend are GBP; contribution units are KPI units and the revenue multiplier is six. Do not fit, build or read predictions. Return only the requested JSON. "
    tasks = []

    def add(
        name,
        dataset,
        question,
        sections,
        expected,
        *,
        channel="",
        window=None,
        fixture=None,
        alternatives=(),
    ):
        tasks.append(
            ResultTask(
                id="fresh_" + name,
                prompt=common + question,
                required_sections=frozenset(sections),
                expected=expected,
                family=name,
                channel=channel,
                fixture=deepcopy(fixture or _fixture(dataset)),
                dataset="fresh_" + dataset,
                evidence_window=window,
                evidence_options=tuple(frozenset(option) for option in alternatives),
            )
        )

    add(
        "inclusive_window",
        "harbour",
        "Across all channels, include both 9 and 16 March 2026 and exclude 2 March. Give revenue, spend and roi (ratio of totals), using keys revenue, spend, roi.",
        {"coefficients"},
        {"revenue": 138, "spend": 48, "roi": 23 / 8},
        window={"start": "2026-03-09", "end": "2026-03-16"},
        alternatives=({"coefficients"}, {"channel_summary"}),
    )
    add(
        "diagnostic_threshold",
        "harbour",
        "Use this reporting rule only: every saved R_hat must be strictly below 1.005. Return passes_requested_rule and max_r_hat. The saved success label does not override this rule.",
        {"r_hat"},
        {"passes_requested_rule": False, "max_r_hat": 1.008},
    )
    add(
        "absent_diagnostics",
        "moor",
        "Inspect saved diagnostic sections. Return convergence='unknown' and reason='not_returned' if neither model_stats nor r_hat is returned. Completion alone is insufficient.",
        {"model_stats", "r_hat"},
        {"convergence": "unknown", "reason": "not_returned"},
    )
    add(
        "signed_reconciliation",
        "harbour",
        "For 9 March, reconcile the saved decomposition in KPI units. Return media_total, non_media_excluding_overlap, overlap and reconstructed_model. Include holiday in non-media; keep Overlap separate.",
        {"contributions", "channel_map"},
        {
            "media_total": 10,
            "non_media_excluding_overlap": 48,
            "overlap": 3,
            "reconstructed_model": 61,
        },
        window={"start": "2026-03-09", "end": "2026-03-09"},
    )
    add(
        "marginal_interval",
        "harbour",
        "For Audio report the saved current-spend marginal ROI median, lower and upper 94% HDI bounds, hdi_prob and current_spend. Preserve a negative bound. Use keys median, lower, upper, hdi_prob, current_spend.",
        {"mroi_summary", "channel_map"},
        {"median": 0.8, "lower": -0.2, "upper": 1.7, "hdi_prob": 0.94, "current_spend": 22},
        channel="Audio_activity",
        alternatives=(
            {"mroi_summary", "channel_map"},
            {"mroi_summary", "verified_channel_identity"},
        ),
    )
    add(
        "optional_history",
        "moor",
        "Request historical marginal ROI periods. If unavailable, give the returned availability and literal reason using keys available and reason. Do not infer a historical value from another section.",
        {"mroi_periods"},
        {"available": False, "reason": "fitted_before_mroi_periods"},
    )
    add(
        "colliding_identity",
        "moor",
        "Outdoor panel and Outdoor digital are separate channels. Use the channel map and return their exact activity identifiers as panel_identifier and digital_identifier. Do not combine them because their normalised aliases collide.",
        {"channel_map"},
        {"panel_identifier": "Outdoor Activity", "digital_identifier": "outdoor_activity"},
    )
    add(
        "zero_spend_convention",
        "moor",
        "For Partnership return revenue, spend and the saved roi. The backend reports ROI=0 when summed spend is zero; preserve this sentinel rather than claiming a defined revenue/spend ratio.",
        {"channel_summary", "channel_map"},
        {"revenue": 24, "spend": 0, "roi": 0},
        channel="Partnership_activity",
        alternatives=({"channel_summary", "channel_map"}, {"coefficients", "channel_map"}),
    )
    return tasks
