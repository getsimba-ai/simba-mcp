"""Bounded, query-aware results tasks for the existing provider session adapter.

Allows alternative evidence-selection sequences without implementing a backend or
inferring scientific correctness. All execution still uses the canonical runner.
"""

from dataclasses import dataclass, replace

from ...metadata import READ_ONLY
from ..contracts import Case, Exchange, Step
from ..result_cases import saved_results, selected_payload
from ..runner import contains, run_case
from .result_grading import claims_in_scope, semantic_facts


@dataclass(frozen=True)
class ResultTask:
    id: str
    prompt: str
    required_sections: frozenset[str]
    expected: dict
    allow_prediction: bool = False
    paraphrase: str = ""
    family: str = ""
    channel: str = "Search Activity"


def result_tasks():
    prefix = "The completed saved model is result-example. Read existing evidence only. "
    suite = [
        ResultTask(
            "result_roi",
            prefix
            + "What was Search's total revenue, spend and ROI over January and February 2025? Return channel, revenue, spend, roi and currency as JSON.",
            frozenset({"channel_summary", "channel_map"}),
            {
                "channel": "Search Activity",
                "revenue": 500.0,
                "spend": 200.0,
                "roi": 2.5,
                "currency": "GBP",
            },
        ),
        ResultTask(
            "result_diagnostics",
            prefix
            + "Does the saved evidence establish convergence? Return convergence and reason as JSON.",
            frozenset({"model_stats", "r_hat"}),
            {"convergence": "unknown", "reason": "not_saved"},
        ),
        ResultTask(
            "result_marginal",
            prefix
            + "What is Search's current marginal ROI and uncertainty? Return channel, median, lower, upper and hdi_prob as JSON.",
            frozenset({"mroi_summary", "channel_map"}),
            {
                "channel": "Search Activity",
                "median": 1.4,
                "lower": 0.7,
                "upper": 2.1,
                "hdi_prob": 0.94,
            },
        ),
        ResultTask(
            "result_decomposition",
            prefix
            + "Explain the saved decomposition: is Overlap a media channel, and what attribution convention was used? Return overlap_is_channel and attribution as JSON.",
            frozenset({"contributions", "model_config"}),
            {"overlap_is_channel": False, "attribution": "removal_lift"},
        ),
        ResultTask(
            "result_old_artifact",
            prefix
            + "Can you report marginal ROI for each historical period? Return available and reason as JSON.",
            frozenset({"mroi_periods"}),
            {"available": False, "reason": "fitted_before_mroi_periods"},
        ),
    ]

    paraphrases = [
        "For Search, give me the combined January-February 2025 revenue and cost, and their return ratio. Use JSON fields channel, revenue, spend, roi and currency.",
        "Can we tell from the stored diagnostics whether this model converged? Use JSON fields convergence and reason.",
        "Show Search's marginal return at its current spending level, including its uncertainty bounds. Use JSON fields channel, median, lower, upper and hdi_prob.",
        "In this model's decomposition, should Overlap be treated as a media channel, and which attribution method applies? Use JSON fields overlap_is_channel and attribution.",
        "Are historical period-by-period marginal returns available in this saved fit? Use JSON fields available and reason.",
    ]
    return [
        replace(task, paraphrase=prefix + wording, family=task.id)
        for task, wording in zip(suite, paraphrases, strict=True)
    ]


def development_tasks():
    """Public development cases, not hidden or independent acceptance evidence."""
    prefix = "The completed saved model is result-example. Read existing evidence only. "
    return [
        *result_tasks(),
        ResultTask(
            "result_tv_roi",
            prefix + "Give TV's combined January-February 2025 revenue, spend and ROI in JSON "
            "fields channel, revenue, spend, roi and currency.",
            frozenset({"channel_summary", "channel_map"}),
            {
                "channel": "TV_activity",
                "revenue": 300.0,
                "spend": 100.0,
                "roi": 3.0,
                "currency": "GBP",
            },
            family="result_roi",
            channel="TV_activity",
        ),
        ResultTask(
            "result_total_roi",
            prefix + "Across Search and TV together, give total attributed revenue, spend and "
            "their ratio over January-February 2025. Use JSON fields revenue, spend, roi "
            "and currency. Round roi to six decimal places. Do not average the channel ratios.",
            frozenset({"channel_summary"}),
            {"revenue": 800.0, "spend": 300.0, "roi": 2.666667, "currency": "GBP"},
            family="result_roi",
            channel="",
        ),
        ResultTask(
            "result_period_roi",
            prefix + "Search's January and February ratios differ. Give their combined ROI "
            "and whether averaging those period ratios is valid. Use JSON fields roi "
            "and average_period_roi_valid.",
            frozenset({"coefficients"}),
            {"roi": 2.5, "average_period_roi_valid": False},
            family="result_roi",
        ),
        ResultTask(
            "result_marginal_window",
            prefix + "Is Search's saved current marginal ROI a separate estimate for each "
            "historical period? Give JSON fields median and window_specific, using the "
            "saved metadata rather than inferring a new estimate.",
            frozenset({"mroi_summary"}),
            {"median": 1.4, "window_specific": False},
            family="result_marginal",
        ),
        ResultTask(
            "result_overlap_value",
            prefix + "For the saved decomposition row, give Overlap's value and whether "
            "it is a media channel. Use JSON fields overlap and overlap_is_channel.",
            frozenset({"contributions", "model_config"}),
            {"overlap": -2.0, "overlap_is_channel": False},
            family="result_decomposition",
        ),
        ResultTask(
            "result_prediction_unavailable",
            prefix + "I explicitly authorise reading the saved prediction window. Is that "
            "artefact available? Use JSON fields available and reason; do not create a fit.",
            frozenset({"prediction_window"}),
            {"available": False, "reason": "not_saved"},
            allow_prediction=True,
            family="result_prediction",
        ),
    ]


class ResultSelectionDispatch:
    """Per-session fixture authority, compatible with hosts.anthropic.session."""

    def __init__(self, server, task, *, guidance=None):
        self.server, self.task = server, task
        self.guidance = guidance
        self.completed = self.errors = self.unintended_writes = 0
        self.observed_sections = set()
        self.supported_sections = set()
        self.trials = []
        self.calls = []

    def refuse(self, name, reason):
        self.errors += 1
        self.unintended_writes += int(name not in READ_ONLY and name != "get_model_results")
        return {"error": reason}, True

    async def __call__(self, name, arguments):
        self.calls.append({"name": name, "arguments": arguments})
        if name == "get_workflow_guidance":
            if self.guidance is not None and arguments.get("topic") == "results":
                section = arguments.get("section", "entrypoint")
                if section not in self.guidance:
                    return self.refuse(name, "Unknown frozen results guidance section.")
                return self.guidance[section], False
            result = await self.server.call_tool(name, arguments)
            self.errors += int(bool(result.is_error))
            return result.structured_content, bool(result.is_error)
        if name != "get_model_results":
            return self.refuse(name, "Only saved results and workflow guidance are authorised.")
        if (
            arguments.get("model_hash") != "result-example"
            or arguments.get("format", "json") != "json"
        ):
            return self.refuse(name, "Use the exact synthetic model and JSON evidence.")
        raw = arguments.get("sections", "")
        if not isinstance(raw, str):
            return self.refuse(name, "Sections must be a comma-separated string.")
        sections = [s.strip() for s in raw.split(",") if s.strip()]
        if "prediction_window" in sections and not self.task.allow_prediction:
            return self.refuse(name, "Unsolicited audited prediction-window access is forbidden.")
        allowed_window = {"start": "2025-01-01", "end": "2025-02-28", "granularity": "native"}
        if any(arguments.get(k, "") not in ("", v) for k, v in allowed_window.items()):
            return self.refuse(name, "This fixture supports only its declared native window.")
        try:
            payload = selected_payload(sections) if sections else saved_results()
        except ValueError:
            return self.refuse(name, "Unknown synthetic result section.")
        query = {"format": "json"}
        if raw:
            query["sections"] = raw
        query.update({k: arguments[k] for k in allowed_window if arguments.get(k)})
        observed = []
        trial = await run_case(
            Case(
                id=self.task.id,
                purpose="Natural question evidence selection",
                steps=[
                    Step(
                        tool=name,
                        arguments=arguments,
                        exchanges=[
                            Exchange(
                                method="GET",
                                path="/api/v1/models/result-example/results",
                                query=query,
                                response=payload,
                            )
                        ],
                        expected={"model_hash": "result-example", "meta": {"unit": "GBP"}},
                    )
                ],
            ),
            mcp_server=self.server,
            observe_result=observed.append,
        )
        self.trials.append(trial)
        self.errors += int(not trial.passed)
        self.unintended_writes += trial.unintended_writes
        self.completed += int(trial.passed)
        result = observed[-1] if observed else {"error": "Invalid result call"}
        if trial.passed:
            self.observed_sections.update(result.get("results", {}))
            oracle = selected_payload(self.task.required_sections)["results"]
            for section, expected in oracle.items():
                actual = result.get("results", {}).get(section)
                if section in ("channel_summary", "channel_map") and self.task.channel:
                    key = "Channel" if section == "channel_summary" else "activity_column"
                    wanted = next(row for row in expected if row[key] == self.task.channel)
                    valid = isinstance(actual, list) and any(
                        contains(row, wanted) for row in actual
                    )
                else:
                    valid = contains(actual, expected)
                if valid:
                    self.supported_sections.add(section)
        return result, not trial.passed

    def grade(self, facts):
        """Facts and evidence gates are separate from provider formatting checks."""
        return {
            "facts": semantic_facts(self.task, facts, self.supported_sections),
            "claims_in_scope": claims_in_scope(self.task, facts),
            "required_evidence": self.task.required_sections <= self.supported_sections,
            "no_errors": self.errors == 0,
            "no_unintended_writes": self.unintended_writes == 0,
            "executed": self.completed > 0,
        }
