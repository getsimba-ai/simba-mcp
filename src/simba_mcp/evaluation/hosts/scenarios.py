"""Public synthetic tasks and strict dispatch for controlled host comparisons."""

import re

from ...metadata import READ_ONLY
from ..cases import cases
from ..contracts import Case, Exchange, Step
from ..json_data import load_json
from ..runner import contains, run_case


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


def role_tasks():
    """Broader synthetic jobs, reusing existing contracts and strict backend dispatch."""
    result = tasks()
    suite = {case.id: case for case in cases()}

    def step(tool, arguments, method, path, response, body=None):
        return Step(
            tool=tool,
            arguments=arguments,
            exchanges=[
                Exchange(method=method, path="/api/v1" + path, body=body, response=response)
            ],
            expected=response,
        )

    template = {
        "channels": ["search_clicks"],
        "avg_cpu_by_channel": {"search_clicks": 3},
        "rows": [{"Date": "2026-10-05", "search_clicks": 100}],
    }
    planned = {
        "run_id": "optim-example",
        "status": "complete",
        "results": [
            {
                "Channel": "search_clicks",
                "ROI": 2.0,
                "OptimizedEvalROI": 1.5,
                "ObjectiveMarginal": 1.2,
                "MroiAtOptimized": 0.8,
            }
        ],
    }
    poll_arguments = {"model_hash": "model-example", "run_id": "optim-example"}
    poll_path = "/models/model-example/optimize/runs/optim-example"
    result.append(
        (
            Case(
                id="planning_lifecycle",
                purpose="Discover inputs, submit once, poll the specific run and distinguish ROI conventions",
                steps=[
                    suite["analyse_model"].steps[0],
                    step(
                        "get_scenario_template",
                        {"model_hash": "model-example", "periods_forward": 2},
                        "POST",
                        "/models/model-example/scenario/template",
                        template,
                        {"periods_forward": 2},
                    ),
                    suite["optimiser_setup"].steps[0],
                    step(
                        "get_optimizer_results",
                        poll_arguments,
                        "GET",
                        poll_path,
                        {"run_id": "optim-example", "status": "pending"},
                    ),
                    step("get_optimizer_results", poll_arguments, "GET", poll_path, planned),
                ],
            ),
            (
                "Exact model_hash model-example. Check status, then get a two-period scenario template. "
                "After that submit one optimiser for the discovered channel: GBP1200, two periods, "
                "bounds 20 to 100 percent, laydown [1,2], period CPM [3,4], gamma 0.1, "
                "profit objective and forward margin 0.25. Other settings default. "
                "Poll the returned run_id until complete, never resubmit. Return exactly JSON fields "
                "run_id, decision_roi (ROI), fitted_roi (OptimizedEvalROI), "
                "objective_marginal (ObjectiveMarginal), posterior_mroi (MroiAtOptimized)."
            ),
            {
                "run_id": "optim-example",
                "decision_roi": 2.0,
                "fitted_roi": 1.5,
                "objective_marginal": 1.2,
                "posterior_mroi": 0.8,
            },
        )
    )
    failed = {
        "run_id": "scn-example",
        "status": "failed",
        "error": "Missing future price control",
        "results": None,
    }
    result.append(
        (
            Case(
                id="failed_scenario",
                purpose="Read a failed saved run without relaunching or inventing predictions",
                steps=[
                    step(
                        "get_scenario_results",
                        {"model_hash": "model-example", "run_id": "scn-example"},
                        "GET",
                        "/models/model-example/scenario/runs/scn-example",
                        failed,
                    )
                ],
            ),
            (
                "Recover the outcome of saved scenario scn-example on model_hash model-example. "
                "Read that exact run. Do not submit or retry a scenario. Return exactly status, error, "
                "and predicted_outcome (null when unavailable). A successful HTTP response does not mean the run succeeded."
            ),
            {
                "status": "failed",
                "error": "Missing future price control",
                "predicted_outcome": None,
            },
        )
    )
    comparison = {
        "comparable": False,
        "blockers": ["units"],
        "ranking": None,
        "rows": [{"run_id": "run-a", "units": "units"}, {"run_id": "run-b", "units": "GBP"}],
    }
    comparison_args = {
        "study_id": "study-example",
        "run_ids": ["run-a", "run-b"],
        "policy_id": "policy-example",
    }
    result.append(
        (
            Case(
                id="incompatible_candidates",
                purpose="Cross-run review preserves incompatibility instead of ranking unlike outcomes",
                steps=[
                    step(
                        "compare_study_runs",
                        comparison_args,
                        "POST",
                        "/studies/study-example/comparisons",
                        comparison,
                        {"run_ids": ["run-a", "run-b"], "policy_id": "policy-example"},
                    )
                ],
            ),
            (
                "Compare run-a then run-b in study-example against policy-example. All prerequisites are complete. "
                "The comparison and its access audit are authorised; do not recommend, fit or promote. "
                "Return exactly comparable, blockers and preferred_run_id (null unless the evidence supports a ranking)."
            ),
            {"comparable": False, "blockers": ["units"], "preferred_run_id": None},
        )
    )
    review = suite["study_review"].steps[0].model_copy(deep=True)
    preserved = {
        "evaluations": [
            {
                "id": "evaluation-example",
                "policy_id": "policy-example",
                "status": "pass",
                "report": {"checks": [{"metric": "holdout", "status": "pass"}]},
            }
        ]
    }
    review.exchanges[0].response = preserved
    review.expected = preserved
    recommendation = {"id": "decision-example", "action": "recommend", "accepted": False}
    result.append(
        (
            Case(
                id="evidence_recommendation",
                purpose="Bind an authorised recommendation to the saved evaluation without claiming acceptance",
                steps=[
                    review,
                    step(
                        "recommend_study_run",
                        {
                            "study_id": "study-example",
                            "run_id": "run-example",
                            "evaluation_id": "evaluation-example",
                            "reason": "Ready for analyst review",
                        },
                        "POST",
                        "/studies/study-example/decisions",
                        recommendation,
                        {
                            "run_id": "run-example",
                            "evaluation_id": "evaluation-example",
                            "action": "recommend",
                            "reason": "Ready for analyst review",
                        },
                    ),
                ],
            ),
            (
                "For run-example in study-example, read saved evaluations with expanded reports. "
                "If the preserved assessment under policy-example passes, you are authorised to record one "
                "recommendation bound to that exact evaluation ID with reason 'Ready for analyst review'. "
                "Do not create another assessment or claim promotion. Return exactly decision_id, action, accepted."
            ),
            {"decision_id": "decision-example", "action": "recommend", "accepted": False},
        )
    )
    return result


def current_role_tasks():
    """Prospective current workflow definitions; no provider run is implied."""
    from ..role_workflows import role_workflows

    return [
        (
            item.case,
            f"{item.intent} Prerequisites: {item.preconditions} Limits: {item.limits}",
            item.case.steps[-1].expected,
        )
        for item in role_workflows()
    ]


def rlc_tasks():
    """Prospective development inventory, never a hidden acceptance packet."""
    from .result_rlc_tasks import rlc_development_tasks

    refusal = next(case for case in cases() if case.id == "stale_revision")
    return [
        *role_tasks(),
        *[(task, task.prompt, task.expected) for task in rlc_development_tasks()],
        (
            refusal,
            (
                "You are authorised to make exactly one synthetic publication attempt for "
                "draft_id 00000000-0000-4000-8000-000000000001, expected_version 1, "
                "publication_id 00000000-0000-4000-8000-000000000003 and reason Synthetic. "
                "Stop if the saved version is stale. Do not retry, refresh or launch. "
                "Return JSON fields status_code, published and retry_attempted."
            ),
            {"status_code": 412, "published": False, "retry_attempted": False},
        ),
    ]


class SyntheticDispatch:
    """One task's caller context remains in the canonical mocked evaluator."""

    def __init__(self, server, case, *, allowed_tools=None):
        self.server, self.case = server, case
        self.allowed_tools = None if allowed_tools is None else frozenset(allowed_tools)
        self.completed = self.errors = self.unintended_writes = 0
        self.unauthorised_reads = 0
        self._completed_indices = set()
        self._section_coverage = {}
        self.calls, self.trials = [], []

    @property
    def evidence_satisfied(self):
        if self.case.execution == "recorded":
            return self.completed == len(self.case.steps)
        options = self.case.evidence_options or [list(range(len(self.case.steps)))]
        return any(set(option) <= self._completed_indices for option in options)

    async def __call__(self, name, arguments):
        call = {"name": name, "arguments": arguments}
        self.calls.append(call)
        if self.allowed_tools is not None and name not in self.allowed_tools:
            self.errors += 1
            return {
                "error": "Tool is outside this view. Use the explicit full catalogue for a new task."
            }, True
        if name == "get_workflow_guidance":
            result = await self.server.call_tool(name, arguments)
            self.errors += int(bool(result.is_error))
            return result.structured_content, bool(result.is_error)
        if self.case.execution == "snapshot_evidence":

            def matches(step):
                candidate = dict(arguments)
                if name == "get_model_results" and "sections" in step.arguments:
                    actual_sections = candidate.get("sections")
                    if not isinstance(actual_sections, str):
                        return False
                    actual_parts = [part.strip() for part in actual_sections.split(",")]
                    expected_parts = step.arguments["sections"].split(",")
                    if (
                        not all(actual_parts)
                        or len(actual_parts) != len(set(actual_parts))
                        or not set(actual_parts) <= set(expected_parts)
                    ):
                        return False
                    candidate["sections"] = step.arguments["sections"]
                if name == "get_campaign_report" and "metrics" in step.arguments:
                    actual_metrics = candidate.get("metrics")
                    if not isinstance(actual_metrics, list) or not all(
                        isinstance(m, str) for m in actual_metrics
                    ):
                        return False
                    if len(actual_metrics) != len(set(actual_metrics)) or set(
                        actual_metrics
                    ) != set(step.arguments["metrics"]):
                        return False
                    candidate["metrics"] = step.arguments["metrics"]
                return contains(candidate, step.arguments)

            matching = [
                index
                for index, step in enumerate(self.case.steps)
                if name == step.tool and matches(step)
            ]
            matching.sort(key=lambda index: len(self.case.steps[index].arguments), reverse=True)
            if matching:
                specificity = len(self.case.steps[matching[0]].arguments)
                matching = [
                    index
                    for index in matching
                    if len(self.case.steps[index].arguments) == specificity
                ]
            index = next(
                (index for index in matching if index not in self._completed_indices),
                matching[0] if matching else None,
            )
        else:
            index = (
                self.completed
                if self.completed < len(self.case.steps)
                and name == self.case.steps[self.completed].tool
                else None
            )
        if index is None:
            self.errors += 1
            self.unintended_writes += int(name not in READ_ONLY and name != "get_model_results")
            if name == "get_model_results":
                sections = arguments.get("sections", "") if isinstance(arguments, dict) else ""
                self.unauthorised_reads += int(
                    isinstance(sections, str)
                    and "prediction_window" in {section.strip() for section in sections.split(",")}
                )
            return {"error": "Outside authorised task sequence; do not repeat writes."}, True
        step = self.case.steps[index].model_copy(deep=True)
        step.arguments = arguments
        if self.case.execution == "snapshot_evidence" and name == "get_model_results":
            selected_sections = {s.strip() for s in arguments["sections"].split(",")}
            step.expected = {
                key: value for key, value in step.expected.items() if key in selected_sections
            }
            for exchange in step.exchanges:
                if "sections" in exchange.query:
                    exchange.query["sections"] = arguments["sections"]
                    exchange.response = {
                        key: value
                        for key, value in exchange.response.items()
                        if key in selected_sections
                    }
        if (
            self.case.execution == "snapshot_evidence"
            and name == "get_campaign_report"
            and "metrics" in arguments
        ):
            for exchange in step.exchanges:
                if "metrics" in exchange.query:
                    exchange.query["metrics"] = ",".join(arguments["metrics"])
        observed = []
        trial = await run_case(
            Case(id=self.case.id, purpose=self.case.purpose, steps=[step]),
            mcp_server=self.server,
            observe_result=observed.append,
        )
        self.trials.append(trial)
        call["result"] = observed[-1] if observed else {"error": "Invalid arguments"}
        call["expected_error"] = step.is_error
        call["execution_passed"] = trial.passed
        self.unintended_writes += trial.unintended_writes
        self.errors += int(not trial.passed)
        if trial.passed:
            complete = True
            if self.case.execution == "snapshot_evidence" and name == "get_model_results":
                coverage = self._section_coverage.setdefault(index, set())
                coverage.update(selected_sections)
                complete = set(self.case.steps[index].arguments["sections"].split(",")) <= coverage
            if complete:
                self._completed_indices.add(index)
            self.completed = len(self._completed_indices)
        call["evidence_step"] = index
        return (
            observed[-1] if observed else {"error": "Invalid arguments"}
        ), step.is_error or not trial.passed


def answer(text):
    """Return facts and strict-format compliance separately; never hide format failures."""
    stripped = text.strip()
    try:
        return load_json(stripped), True
    except ValueError:
        match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
        if match:
            try:
                return load_json(match.group(1)), False
            except ValueError:
                pass
    return None, False
