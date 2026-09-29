"""Bounded, query-aware results tasks for the existing provider session adapter.

Allows alternative evidence-selection sequences without implementing a backend or
inferring scientific correctness. All execution still uses the canonical runner.
"""

from dataclasses import dataclass

from ...metadata import READ_ONLY
from ..contracts import Case, Exchange, Step
from ..result_cases import saved_results, selected_payload
from ..runner import contains, run_case


@dataclass(frozen=True)
class ResultTask:
    id: str
    prompt: str
    required_sections: frozenset[str]
    expected: dict
    allow_prediction: bool = False


def result_tasks():
    prefix = "The completed saved model is result-example. Read existing evidence only. "
    return [
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
            frozenset({"contributions", "model_config", "channel_map"}),
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
                if section in ("channel_summary", "channel_map"):
                    # These tasks concern Search; filtering out TV is valid.
                    key = "Channel" if section == "channel_summary" else "activity_column"
                    wanted = next(row for row in expected if row[key] == "Search Activity")
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
            "facts": isinstance(facts, dict)
            and all(facts.get(k) == v for k, v in self.task.expected.items()),
            "required_evidence": self.task.required_sections <= self.supported_sections,
            "no_errors": self.errors == 0,
            "no_unintended_writes": self.unintended_writes == 0,
            "executed": self.completed > 0,
        }
