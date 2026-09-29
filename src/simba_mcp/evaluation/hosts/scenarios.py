"""Public synthetic tasks and strict dispatch for controlled host comparisons."""

import json
import re

from ...metadata import READ_ONLY
from ..cases import cases
from ..contracts import Case
from ..runner import run_case


def tasks():
    suite = {case.id: case for case in cases()}
    analysis = suite["analyse_model"]
    analysis.steps[1].arguments["sections"] = "channel_summary"
    analysis.steps[1].exchanges[0].query["sections"] = "channel_summary"
    result = [
        (
            analysis,
            (
                "The exact model_hash is model-example, not a display name. Check its status first, then retrieve only channel_summary JSON results. "
                "Return exactly channel, roi, contribution_share, unit and interval from the saved evidence as a single JSON object. Do not invent an interval probability."
            ),
            {
                "channel": "search_clicks",
                "roi": 2.0,
                "contribution_share": 0.1,
                "unit": "units",
                "interval": [0.05, 0.15],
            },
        ),
        (
            suite["optimiser_setup"],
            (
                "The exact model_hash is model-example (preserve the entire string). It is complete and capabilities/preflights are checked. "
                "Submit one optimiser run, no polling. Channel search_clicks, GBP1200 over two periods, "
                "bounds 20 to 100 percent, laydown weights [1,2], period CPM [3,4], gamma 0.1. "
                "Profit objective, forward margin 0.25, other settings default. Return run_id."
            ),
            {"run_id": "optim-example"},
        ),
        (
            suite["study_review"],
            (
                "The exact run_id is run-example. Review its saved evaluations, expanding reports. "
                "Do not evaluate, recommend, publish or write. Return the saved holdout check as JSON "
                "with metric, status and basis. Missing evidence must remain unevaluated."
            ),
            {"metric": "holdout", "status": "not_evaluated", "basis": {"reason": "not_collected"}},
        ),
    ]
    combined = Case(
        id="cross_domain",
        purpose="Read results then study evidence without writing",
        steps=analysis.steps + suite["study_review"].steps,
    )
    result.append(
        (
            combined,
            (
                "Exact model_hash model-example and run_id run-example. First check model status, "
                "then fetch only channel_summary results, then read study run evaluations with "
                "expanded reports. Do not write or infer missing evidence. Return exactly two "
                "JSON fields: roi from the sole channel, and holdout_status from the saved check."
            ),
            {"roi": 2.0, "holdout_status": "not_evaluated"},
        )
    )
    return result


class SyntheticDispatch:
    """One task's caller context remains in the canonical mocked evaluator."""

    def __init__(self, server, case):
        self.server, self.case = server, case
        self.completed = self.errors = self.unintended_writes = 0

    async def __call__(self, name, arguments):
        if name == "get_workflow_guidance":
            result = await self.server.call_tool(name, arguments)
            self.errors += int(bool(result.is_error))
            return result.structured_content, bool(result.is_error)
        if self.completed >= len(self.case.steps) or name != self.case.steps[self.completed].tool:
            self.errors += 1
            self.unintended_writes += int(name not in READ_ONLY)
            return {"error": "Outside authorised task sequence; do not repeat writes."}, True
        step = self.case.steps[self.completed].model_copy(deep=True)
        step.arguments = arguments
        observed = []
        trial = await run_case(
            Case(id=self.case.id, purpose=self.case.purpose, steps=[step]),
            mcp_server=self.server,
            observe_result=observed.append,
        )
        self.unintended_writes += trial.unintended_writes
        self.errors += int(not trial.passed)
        self.completed += int(trial.passed)
        return (observed[-1] if observed else {"error": "Invalid arguments"}), not trial.passed


def answer(text):
    """Return facts and strict-format compliance separately; never hide format failures."""
    stripped = text.strip()
    try:
        return json.loads(stripped), True
    except ValueError:
        match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1)), False
            except ValueError:
                pass
    return None, False
