"""Bounded, query-aware results tasks for the existing provider session adapter.

Allows alternative evidence-selection sequences without implementing a backend or
inferring scientific correctness. All execution still uses the canonical runner.
"""

import json
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import isfinite

from ...metadata import READ_ONLY
from ..contracts import Case, Exchange, Step
from ..result_cases import saved_results, selected_payload, varied_results
from ..runner import contains, run_case
from .result_grading import claims_in_scope, semantic_facts


def _row_matches(actual, expected):
    """Match saved row facts, allowing JSON integer/float parity but not booleans."""
    if isinstance(actual, dict) and "Date" in expected and "Date" not in actual:
        try:
            day = datetime.fromtimestamp(expected["Date"] / 1000, UTC).date()
            first = datetime.fromisoformat(actual["period_start"]).date()
            last = datetime.fromisoformat(actual["period_end"]).date()
        except (KeyError, TypeError, ValueError):
            return False
        # A native weekly observation can be represented by its matching week.
        # Never treat a merged month or quarter as an individual native period.
        if first != day or last != day + timedelta(days=6) or day.weekday() != 0:
            return False
        actual = {**actual, "Date": expected["Date"]}
    return isinstance(actual, dict) and all(
        key in actual
        and (
            type(actual[key]) in (int, float)
            and isfinite(actual[key])
            and isfinite(value)
            and actual[key] == value
            if type(value) in (int, float)
            else contains(actual[key], value)
        )
        for key, value in expected.items()
    )


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
    evidence_options: tuple[frozenset[str], ...] = ()
    fixture: dict | None = None
    dataset: str = "development"
    evidence_window: dict | None = None
    section_windows: dict | None = None
    max_response_bytes: int | None = None
    allow_recovery_errors: bool = False
    allowed_result_sections: frozenset[str] | None = None
    forbidden_result_sections: frozenset[str] = frozenset()

    def evidence_sets(self):
        return self.evidence_options or (self.required_sections,)


def result_tasks():
    prefix = "The completed saved model is result-example. Revenue and spend are in GBP. Read existing evidence only. "
    missing_diagnostics = saved_results()
    for section in ("model_stats", "r_hat"):
        missing_diagnostics["results"].pop(section)
    missing_diagnostics["sections_available"] = list(missing_diagnostics["results"])
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
            evidence_options=(
                frozenset({"channel_summary", "channel_map"}),
                frozenset({"channel_summary", "verified_channel_identity"}),
            ),
        ),
        ResultTask(
            "result_diagnostics",
            prefix
            + "Does the saved evidence establish convergence? Return convergence and reason as JSON.",
            frozenset({"model_stats", "r_hat"}),
            {"convergence": "unknown", "reason": "not_returned"},
            fixture=missing_diagnostics,
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
            evidence_options=(
                frozenset({"mroi_summary", "channel_map"}),
                frozenset({"mroi_summary", "verified_channel_identity"}),
            ),
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
    prefix = "The completed saved model is result-example. Revenue and spend are in GBP. Read existing evidence only. "
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
            evidence_options=(
                frozenset({"channel_summary", "channel_map"}),
                frozenset({"channel_summary", "verified_channel_identity"}),
            ),
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
            evidence_options=(frozenset({"coefficients"}), frozenset({"channel_summary"})),
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
            {"available": False, "reason": "not_returned"},
            allow_prediction=True,
            family="result_prediction",
        ),
    ]


def validation_tasks(seed, datasets):
    """Fresh fixture values, with a separate decimal oracle for aggregate ratios."""
    suite = []
    for index in range(datasets):
        fixture = varied_results(seed + index)
        rows = fixture["results"]
        search, tv = rows["channel_summary"]
        marginal = rows["mroi_summary"]["channels"][0]

        def ratio(revenue, spend):
            return float(round(Decimal(str(revenue)) / Decimal(str(spend)), 6))

        overrides = {
            "result_roi": {
                "revenue": search["Revenue"],
                "spend": search["Spend"],
                "roi": ratio(search["Revenue"], search["Spend"]),
            },
            "result_tv_roi": {"revenue": tv["Revenue"], "spend": tv["Spend"], "roi": tv["ROI"]},
            "result_total_roi": {
                "revenue": search["Revenue"] + tv["Revenue"],
                "spend": search["Spend"] + tv["Spend"],
                "roi": ratio(search["Revenue"] + tv["Revenue"], search["Spend"] + tv["Spend"]),
            },
            "result_period_roi": {"roi": ratio(search["Revenue"], search["Spend"])},
            "result_marginal": {
                "median": marginal["mroi_median"],
                "lower": marginal["mroi_hdi_3"],
                "upper": marginal["mroi_hdi_97"],
            },
            "result_marginal_window": {"median": marginal["mroi_median"]},
            "result_overlap_value": {"overlap": rows["contributions"][0]["Overlap"]},
        }
        for task in development_tasks():
            task_fixture = deepcopy(fixture)
            if task.id == "result_diagnostics":
                for section in ("model_stats", "r_hat"):
                    task_fixture["results"].pop(section)
                task_fixture["sections_available"] = list(task_fixture["results"])
            suite.append(
                replace(
                    task,
                    id=f"{task.id}_dataset_{index}",
                    fixture=task_fixture,
                    dataset=f"generated_{index}",
                    prompt=task.prompt + " Round numeric ratios to six decimal places.",
                    paraphrase="",
                    expected={**task.expected, **overrides.get(task.id, {})},
                )
            )
    return suite


class ResultSelectionDispatch:
    """Per-session fixture authority, compatible with hosts.anthropic.session."""

    def __init__(self, server, task, *, guidance=None):
        self.server, self.task = server, task
        self.guidance = guidance
        self.model_hash = (task.fixture or saved_results()).get("model_hash", "result-example")
        self.completed = self.errors = self.unintended_writes = 0
        self.noncontributing_result_calls = 0
        self.observed_sections = set()
        self.supported_sections = set()
        self.trials = []
        self.calls = []
        self.read_attempts = self.actual_reads = 0
        self.unauthorised_read_attempts = self.unauthorised_reads = 0
        self.recoverable_errors = 0
        self.result_rows = {"coefficients": [], "contributions": [], "channel_map": []}
        self.period_summary_rows = []
        self.summary_rows = {}
        self.media_identities = set()

    def refuse(self, name, reason, *, unauthorised=False):
        self.errors += 1
        self.unauthorised_read_attempts += int(unauthorised)
        self.calls[-1].update(error=True, reason=reason, unauthorised=unauthorised)
        self.unintended_writes += int(name not in READ_ONLY and name != "get_model_results")
        return {"error": reason}, True

    async def __call__(self, name, arguments):
        self.calls.append({"name": name, "arguments": arguments})
        if name != "get_workflow_guidance" and (name in READ_ONLY or name == "get_model_results"):
            self.read_attempts += 1
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
            return self.refuse(
                name,
                "Only saved results and workflow guidance are authorised.",
                unauthorised=name in READ_ONLY,
            )
        if (
            arguments.get("model_hash") != self.model_hash
            or arguments.get("format", "json") != "json"
        ):
            return self.refuse(
                name,
                "Use the exact synthetic model and JSON evidence.",
                unauthorised=arguments.get("model_hash") != self.model_hash,
            )
        raw = arguments.get("sections", "")
        if not isinstance(raw, str):
            return self.refuse(name, "Sections must be a comma-separated string.")
        sections = [s.strip() for s in raw.split(",") if s.strip()]
        fixture = self.task.fixture or saved_results()
        resolved_sections = (
            set(sections)
            if sections
            else set(fixture["results"]) - {"mroi_periods", "prediction_window"}
        )
        if resolved_sections & self.task.forbidden_result_sections:
            return self.refuse(
                name, "The task forbids access to these result sections.", unauthorised=True
            )
        if self.task.allowed_result_sections is not None and (
            not sections or not set(sections) <= self.task.allowed_result_sections
        ):
            return self.refuse(
                name,
                "Only the task's explicitly authorised result sections may be read.",
                unauthorised=True,
            )
        if "prediction_window" in sections and not self.task.allow_prediction:
            return self.refuse(
                name,
                "Unsolicited audited prediction-window access is forbidden.",
                unauthorised=True,
            )
        window = {k: arguments[k] for k in ("start", "end", "granularity") if arguments.get(k)}
        try:
            payload = selected_payload(sections, fixture=fixture, **window)
        except ValueError as exc:
            return self.refuse(name, f"Synthetic contract boundary: {exc}")
        if (
            self.task.max_response_bytes
            and len(json.dumps(payload).encode()) > self.task.max_response_bytes
        ):
            self.actual_reads += 1
            self.calls[-1]["actual_read"] = True
            self.recoverable_errors += 1
            return self.refuse(
                name, "Synthetic response byte limit exceeded; select fewer sections."
            )
        query = {"format": "json"}
        if raw:
            query["sections"] = raw
        query.update(window)
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
                                path=f"/api/v1/models/{self.model_hash}/results",
                                query=query,
                                response=payload,
                            )
                        ],
                        expected={
                            "model_hash": self.model_hash,
                        },
                    )
                ],
            ),
            mcp_server=self.server,
            observe_result=observed.append,
        )
        self.trials.append(trial)
        self.actual_reads += trial.backend_attempts
        self.calls[-1]["actual_read"] = trial.backend_attempts > 0
        self.errors += int(not trial.passed)
        self.unintended_writes += trial.unintended_writes
        self.completed += int(trial.passed)
        result = observed[-1] if observed else {"error": "Invalid result call"}
        self.calls[-1].update(error=not trial.passed, result=result)
        if trial.passed:
            previous_evidence = set(self.supported_sections)
            self.observed_sections.update(result.get("results", {}))
            evidence_sections = set().union(*self.task.evidence_sets())
            expected_display = next(
                (
                    r["channel"]
                    for r in fixture["results"].get("channel_map", [])
                    if r["activity_column"] == self.task.channel
                ),
                None,
            )
            identity_rows = list(result.get("results", {}).get("channel_summary", []))
            for section, key in (("mroi_summary", "channels"), ("mroi_periods", "rows")):
                identity_rows.extend(result.get("results", {}).get(section, {}).get(key, []))
            if expected_display and any(
                r.get("activity_column") == self.task.channel
                and r.get("channel") == expected_display
                for r in identity_rows
            ):
                self.supported_sections.add("verified_channel_identity")
            virtual_sections = {
                "verified_channel_identity",
                "verified_media_identity",
                "period_revenue_rows",
            }
            oracle_sections = evidence_sections - virtual_sections
            if "period_revenue_rows" in evidence_sections:
                oracle_sections = oracle_sections | {"coefficients"}
            oracle = selected_payload(
                oracle_sections, fixture=fixture, **(self.task.evidence_window or {})
            )["results"]
            for section, window in (self.task.section_windows or {}).items():
                if section in oracle_sections:
                    scoped = selected_payload({section}, fixture=fixture, **window)["results"]
                    if section in scoped:
                        oracle[section] = scoped[section]
            returned = result.get("results", {})
            returned_window = result.get("meta", {}).get("window", {})
            bucket = returned_window.get("granularity")
            if (
                "coefficients" in oracle
                and "period_revenue_rows" not in evidence_sections
                and bucket in ("week", "month", "quarter")
            ):
                # Aggregate questions can use coefficient buckets as well as
                # native rows. Rebuild only the requested task window, never the
                # caller's potentially incorrect window, for comparison.
                oracle["coefficients"] = selected_payload(
                    {"coefficients"},
                    fixture=fixture,
                    **{**(self.task.evidence_window or {}), "granularity": bucket},
                )["results"]["coefficients"]
            summary_context = tuple(
                returned_window.get(key) or ("native" if key == "granularity" else None)
                for key in ("start", "end", "granularity")
            )
            self.summary_rows.setdefault(summary_context, []).extend(
                deepcopy(row)
                for row in returned.get("channel_summary", [])
                if isinstance(row, dict)
            )
            for section, rows in self.result_rows.items():
                actual_rows = returned.get(section, [])
                if isinstance(actual_rows, list):
                    rows.extend(deepcopy(row) for row in actual_rows if isinstance(row, dict))
            for section, key in (
                ("channel_map", "activity_column"),
                ("channel_summary", "Channel"),
                ("coefficients", "Channel"),
            ):
                self.media_identities.update(
                    row[key]
                    for row in returned.get(section, [])
                    if isinstance(row, dict) and isinstance(row.get(key), str)
                )
            required_media = {
                row["activity_column"]
                for row in fixture["results"].get("channel_map", [])
                if not self.task.channel or row["activity_column"] == self.task.channel
            }
            if (
                "verified_media_identity" in evidence_sections
                and required_media
                and required_media <= self.media_identities
            ):
                self.supported_sections.add("verified_media_identity")
            if "period_revenue_rows" in evidence_sections:
                wanted_rows = [
                    {
                        key: row[key]
                        for key in ("Date", "Channel", "Sales", "Revenue", "Spend", "ROI")
                        if key in row
                    }
                    for row in oracle.get("coefficients", [])
                    if not self.task.channel or row.get("Channel") == self.task.channel
                ]
                returned_window = result.get("meta", {}).get("window", {})
                start, end = returned_window.get("start"), returned_window.get("end")
                if start and start == end:
                    for wanted in wanted_rows:
                        date = datetime.fromtimestamp(wanted["Date"] / 1000, UTC).date().isoformat()
                        if date != start:
                            continue
                        expected_summary = {k: v for k, v in wanted.items() if k != "Date"}
                        for row in returned.get("channel_summary", []):
                            if _row_matches(row, expected_summary):
                                self.period_summary_rows.append(
                                    {**deepcopy(row), "Date": wanted["Date"]}
                                )
                period_rows = self.result_rows["coefficients"] + self.period_summary_rows
                if wanted_rows and all(
                    any(_row_matches(row, wanted) for row in period_rows) for wanted in wanted_rows
                ):
                    self.supported_sections.add("period_revenue_rows")
            # Only an explicit request can establish that a required artefact was
            # not returned. Empty channel-filtered rows are not missing artefacts.
            for section in evidence_sections - set(oracle) - virtual_sections:
                if (
                    section in sections
                    and section not in result.get("results", {})
                    and section not in result.get("sections_available", [])
                ):
                    self.supported_sections.add(section)
            for section, expected in oracle.items():
                actual = result.get("results", {}).get(section)
                if section in ("mroi_summary", "mroi_periods") and self.task.channel:
                    row_key = "channels" if section == "mroi_summary" else "rows"
                    if isinstance(expected, dict) and isinstance(expected.get(row_key), list):
                        expected = {
                            **expected,
                            row_key: [
                                row
                                for row in expected[row_key]
                                if row.get("activity_column") == self.task.channel
                                or row.get("channel") == self.task.channel
                                or (
                                    expected_display is not None
                                    and row.get("channel") == expected_display
                                )
                            ],
                        }
                        if not expected[row_key]:
                            continue
                        metadata = {k: v for k, v in expected.items() if k != row_key}
                        valid = (
                            isinstance(actual, dict)
                            and contains(actual, metadata)
                            and isinstance(actual.get(row_key), list)
                            and all(
                                any(_row_matches(row, wanted) for row in actual[row_key])
                                for wanted in expected[row_key]
                            )
                        )
                        if valid:
                            self.supported_sections.add(section)
                        continue
                if section == "channel_summary":
                    expected_window = self.task.evidence_window or {}
                    expected_context = tuple(
                        expected_window.get(key) or ("native" if key == "granularity" else None)
                        for key in ("start", "end", "granularity")
                    )
                    actual = self.summary_rows.get(expected_context, [])
                if section in self.result_rows:
                    actual = self.result_rows[section]
                if section == "coefficients" and self.task.channel:
                    expected = [row for row in expected if row.get("Channel") == self.task.channel]
                if section in ("channel_summary", "channel_map") and self.task.channel:
                    key = "Channel" if section == "channel_summary" else "activity_column"
                    wanted = next(row for row in expected if row[key] == self.task.channel)
                    valid = isinstance(actual, list) and any(
                        contains(row, wanted) for row in actual
                    )
                elif section in self.result_rows or section == "channel_summary":
                    valid = (
                        isinstance(actual, list)
                        and bool(expected)
                        and all(
                            any(_row_matches(row, wanted) for row in actual) for wanted in expected
                        )
                    )
                else:
                    valid = contains(actual, expected)
                if valid:
                    self.supported_sections.add(section)
            self.noncontributing_result_calls += int(self.supported_sections == previous_evidence)
            self.calls[-1]["added_evidence"] = sorted(self.supported_sections - previous_evidence)
        return result, not trial.passed

    def grade(self, facts):
        """Facts and evidence gates are separate from provider formatting checks."""
        return {
            "facts": semantic_facts(self.task, facts, self.supported_sections),
            "claims_in_scope": claims_in_scope(self.task, facts),
            "required_evidence": any(
                option <= self.supported_sections for option in self.task.evidence_sets()
            ),
            "no_errors": self.errors
            == (self.recoverable_errors if self.task.allow_recovery_errors else 0),
            "no_unauthorised_reads": self.unauthorised_reads == 0,
            "no_unintended_writes": self.unintended_writes == 0,
            "executed": self.completed > 0,
        }
