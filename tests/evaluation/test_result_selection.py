"""Result questions allow different valid sequences but reject evidence-free passes."""

import pytest

from simba_mcp.evaluation.hosts.result_selection import (
    ResultSelectionDispatch,
    advertised_result_tools,
    prompt_names_model,
    result_tasks,
)
from simba_mcp.evaluation.result_cases import result_cases, saved_results
from simba_mcp.evaluation.runner import run_case
from simba_mcp.server import create_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("case", result_cases(), ids=lambda c: c.id)
async def test_result_contracts(case):
    trial = await run_case(case)
    assert trial.passed, trial.assertions


def test_roi_oracle_and_reconciliation():
    result = saved_results()["results"]
    periods = [r for r in result["coefficients"] if r["Channel"] == "Search Activity"]
    assert sum(r["Revenue"] for r in periods) / sum(r["Spend"] for r in periods) == 2.5
    assert sum(r["ROI"] for r in periods) / len(periods) != 2.5
    row = result["contributions"][0]
    assert (
        sum(row[k] for k in ("Search Activity", "TV_activity", "Base", "price", "Overlap"))
        == row["Model"]
    )


def test_named_hash_hides_tools_the_result_host_refuses():
    from types import SimpleNamespace

    tools = [
        SimpleNamespace(name=name)
        for name in (
            "list_models",
            "get_model",
            "get_model_results",
            "get_workflow_guidance",
            "create_model",
        )
    ]
    named = advertised_result_tools(
        tools,
        "In synthetic_v4_gallery there is no Overlap column.",
        "synthetic_v4_gallery",
    )
    assert [tool.name for tool in named] == ["get_model_results", "get_workflow_guidance"]
    unknown = advertised_result_tools(
        tools, "Which saved model should I read?", "synthetic_v4_gallery"
    )
    assert [tool.name for tool in unknown] == [tool.name for tool in tools]
    assert not prompt_names_model("not-synthetic_v4_gallery-extra", "synthetic_v4_gallery")
    assert prompt_names_model("The completed saved model is result-example.", "result-example")
    assert not prompt_names_model("result-example-extra", "result-example")
    assert not prompt_names_model("", "result-example")


@pytest.mark.anyio
@pytest.mark.parametrize("task", result_tasks(), ids=lambda t: t.id)
async def test_alternative_sequences_and_answer_faults(task):
    server = create_server("compact")
    for split in (True, False):
        dispatch = ResultSelectionDispatch(server, task)
        assert not all(dispatch.grade(task.expected).values())
        groups = (
            sorted(task.required_sections) if split else [",".join(sorted(task.required_sections))]
        )
        for group in groups:
            _, error = await dispatch(
                "get_model_results", {"model_hash": "result-example", "sections": group}
            )
            assert not error
        assert all(dispatch.grade(task.expected).values())
        assert not dispatch.grade({})["facts"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "name,args",
    [
        ("get_data_schema", {}),
        ("create_model", {}),
        ("get_model_results", {"model_hash": "other"}),
        ("get_model_results", {"model_hash": "result-example", "sections": "prediction_window"}),
        ("get_model_results", {"model_hash": "result-example", "granularity": "invalid"}),
    ],
)
async def test_outside_task_requests_fail(name, args):
    dispatch = ResultSelectionDispatch(create_server(), result_tasks()[0])
    _, error = await dispatch(name, args)
    assert error
    assert not all(dispatch.grade(dispatch.task.expected).values())


@pytest.mark.anyio
async def test_payload_measurements_compare_same_facts():
    task = result_tasks()[0]
    full = ResultSelectionDispatch(create_server(), task)
    selective = ResultSelectionDispatch(create_server(), task)
    await full("get_model_results", {"model_hash": "result-example"})
    await selective(
        "get_model_results",
        {"model_hash": "result-example", "sections": "channel_summary,channel_map"},
    )
    assert all(full.grade(task.expected).values())
    assert all(selective.grade(task.expected).values())
    assert selective.trials[0].content_json_bytes < full.trials[0].content_json_bytes
    assert selective.trials[0].backend_downloaded_bytes < full.trials[0].backend_downloaded_bytes


@pytest.mark.anyio
async def test_empty_filtered_evidence_cannot_support_a_correct_guessed_answer():
    task = result_tasks()[0]
    dispatch = ResultSelectionDispatch(create_server(), task)
    await dispatch(
        "get_model_results",
        {
            "model_hash": "result-example",
            "sections": "channel_summary,channel_map",
            "channels": ["missing"],
        },
    )
    assert dispatch.grade(task.expected)["facts"]
    assert not dispatch.grade(task.expected)["required_evidence"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "section,row_key", [("mroi_summary", "channels"), ("mroi_periods", "rows")]
)
@pytest.mark.parametrize("requested", ["Search Activity", "TV_activity", "missing"])
async def test_marginal_evidence_requires_task_channel_not_unrelated_channels(
    section, row_key, requested
):
    from dataclasses import replace

    fixture = saved_results()
    fixture["results"][section] = {
        "available": True,
        row_key: [
            {"channel": "Search", "activity_column": "Search Activity", "mroi_mean": 2.0},
            {"channel": "TV", "activity_column": "TV_activity", "mroi_mean": 1.0},
        ],
    }
    task = replace(
        result_tasks()[0],
        fixture=fixture,
        channel="Search Activity",
        required_sections=frozenset({section}),
        evidence_options=(),
    )
    dispatch = ResultSelectionDispatch(create_server(), task)
    await dispatch(
        "get_model_results",
        {"model_hash": "result-example", "sections": section, "channels": [requested]},
    )
    assert dispatch.grade(task.expected)["required_evidence"] == (requested == "Search Activity")


@pytest.mark.anyio
async def test_changed_answer_is_detected_after_valid_evidence():
    task = result_tasks()[0]
    dispatch = ResultSelectionDispatch(create_server(), task)
    await dispatch(
        "get_model_results",
        {"model_hash": "result-example", "sections": "channel_summary,channel_map"},
    )
    assert not dispatch.grade({**task.expected, "roi": 3.0})["facts"]


@pytest.mark.anyio
@pytest.mark.parametrize("robust,acceptance", [(False, False), (True, False), (True, True)])
async def test_guidance_comparison_freezes_arms_and_uses_real_dispatch(
    tmp_path, monkeypatch, robust, acceptance
):
    import json
    from types import SimpleNamespace

    import httpx

    from simba_mcp.evaluation.hosts import __main__ as command
    from simba_mcp.guidance import read_guidance

    seen = []
    task = result_tasks()[0]
    if acceptance:
        from simba_mcp.evaluation import result_acceptance

        monkeypatch.setattr(result_acceptance, "acceptance_tasks", lambda: [task])

    def respond(request):
        body = json.loads(request.content)
        seen.append(body)
        if len(body["messages"]) == 1:
            content = [
                {
                    "type": "tool_use",
                    "id": "read",
                    "name": "get_model_results",
                    "input": {
                        "model_hash": "result-example",
                        "sections": "channel_summary,channel_map",
                    },
                }
            ]
            stop = "tool_use"
        else:
            content = [{"type": "text", "text": json.dumps(task.expected)}]
            stop = "end_turn"
        return httpx.Response(
            200,
            json={
                "content": content,
                "stop_reason": stop,
                "usage": {"input_tokens": 20, "output_tokens": 10},
            },
        )

    monkeypatch.setattr(
        command, "client", lambda _: httpx.AsyncClient(transport=httpx.MockTransport(respond))
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-key")
    baseline = {
        s: read_guidance("results", s) for s in ("entrypoint", "interpretation", "tool-reference")
    }
    baseline["entrypoint"]["content"] = "Frozen baseline marker"
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline))
    output = tmp_path / "report.json"
    await command.run(
        SimpleNamespace(
            output=output,
            cap_usd=10,
            prior_usd=0,
            mode="eager",
            samples=2,
            case=task.id,
            role_comparison=None,
            results_baseline=baseline_path,
            results_robust=robust,
            results_acceptance=acceptance,
            case_review={"verified": True, "guidance_unchanged": True},
        )
    )
    report = json.loads(output.read_text())
    assert [t["view"] for t in report["trials"]] == [
        "baseline",
        "candidate",
        "candidate",
        "baseline",
    ]
    assert all(t["passed"] for t in report["trials"])
    named = {"get_model_results", "get_workflow_guidance"}
    assert all(set(t["tool_names"]) == named for t in report["trials"])
    assert all(t["result_tool_exposure"] == "named_hash" for t in report["trials"])
    assert all({tool["name"] for tool in request["tools"]} == named for request in seen)
    assert len({t["definitions_sha256"] for t in report["trials"]}) == 1
    assert "Frozen baseline marker" in seen[0]["system"]
    assert "Frozen baseline marker" not in seen[2]["system"]
    assert all(request["messages"][0] == seen[0]["messages"][0] for request in seen)
    assert report["budget"]["reserved"] == 0
    if robust:
        assert report["calibration"]["passed"]
        assert report["frozen_experiment"]["source_sha256"]
        assert report["assessment"]["status"] == "development_only"
        assert not report["assessment"]["accepted"]


@pytest.mark.anyio
async def test_on_demand_guidance_cannot_leak_other_arm():
    frozen = {"entrypoint": {"content": "baseline-only"}}
    dispatch = ResultSelectionDispatch(create_server(), result_tasks()[0], guidance=frozen)
    result, error = await dispatch("get_workflow_guidance", {"topic": "results"})
    assert not error and result == frozen["entrypoint"]


def test_semantic_grader_keeps_literal_and_evidence_constraints_separate():
    from simba_mcp.evaluation.hosts.result_grading import literal_fields, semantic_facts

    roi, diagnostics, marginal, decomposition, old = result_tasks()
    display = {**roi.expected, "channel": "Search"}
    assert semantic_facts(roi, display, {"channel_map"})
    assert not semantic_facts(roi, display, set())
    assert not literal_fields(roi, display)
    assert not semantic_facts(roi, {**display, "roi": 3.0}, {"channel_map"})
    assert not semantic_facts(marginal, {**marginal.expected, "hdi_prob": 0.95}, set())
    assert not semantic_facts(
        decomposition, {"overlap_is_channel": 0, "attribution": "removal_lift"}, set()
    )
    for facts in [
        {"convergence": False, "reason": "Both diagnostic sections were not returned."},
        {"convergence": "unknown", "reason": "not_returned"},
        {"convergence_established": False, "reason": "The diagnostics are unavailable."},
        {"convergence_established": False, "reason": "Diagnostics were not returned."},
    ]:
        assert semantic_facts(diagnostics, facts, set())
    for facts in [
        {"convergence": 0, "reason": "not_returned"},
        {"convergence": "pass", "reason": "not_returned"},
        {"convergence": "failed", "reason": "not_returned"},
        {"convergence_established": 0, "reason": "not_returned"},
        {"convergence_established": True, "reason": "not_returned"},
        {"convergence": "unknown", "convergence_established": True, "reason": "not_returned"},
        {"convergence": "unknown", "reason": "r_hat_too_high"},
    ]:
        assert not semantic_facts(diagnostics, facts, set())
    assert semantic_facts(old, {"mroi_periods": old.expected}, set())
    assert not semantic_facts(old, {"available": True, "mroi_periods": old.expected}, set())
    assert not semantic_facts(old, {"available": False, "reason": "no_spend"}, set())


def test_paraphrases_are_frozen_before_trial_and_preserve_expected_contract():
    for task in result_tasks():
        assert task.paraphrase and task.paraphrase != task.prompt
        assert "result-example" in task.paraphrase


def test_diagnostic_equivalences_do_not_override_a_different_expected_gate():
    from dataclasses import replace

    from simba_mcp.evaluation.hosts.result_grading import fact_verdict, semantic_facts

    missing = result_tasks()[1]
    for expected in (
        {"convergence": "failed", "reason": "r_hat_above_declared_limit"},
        {"convergence": True, "reason": "all_declared_gates_pass"},
        {**missing.expected, "diagnostic_count": 0},
    ):
        task = replace(missing, expected=expected)
        assert semantic_facts(task, expected, set())
        assert not semantic_facts(task, missing.expected, set())
        assert fact_verdict(task, missing.expected, set()) == "fail"


@pytest.mark.anyio
async def test_subset_window_evidence_accepts_window_totals_or_complete_period_rows():
    from dataclasses import replace

    task = replace(
        result_tasks()[0],
        channel="",
        required_sections=frozenset({"channel_summary"}),
        evidence_options=(frozenset({"channel_summary"}), frozenset({"coefficients"})),
        evidence_window={"start": "2025-02-01", "end": "2025-02-28"},
    )
    for sections, window, expected in (
        ("channel_summary", {}, False),
        ("channel_summary", {"start": "2025-01-01", "end": "2025-01-31"}, False),
        ("channel_summary", task.evidence_window, True),
        ("coefficients", {}, True),
        ("coefficients", {"start": "2025-01-01", "end": "2025-01-31"}, False),
    ):
        dispatch = ResultSelectionDispatch(create_server(), task)
        await dispatch(
            "get_model_results", {"model_hash": "result-example", "sections": sections, **window}
        )
        assert dispatch.grade(task.expected)["required_evidence"] is expected


@pytest.mark.anyio
async def test_refused_read_attempts_are_not_executed_reads():
    dispatch = ResultSelectionDispatch(create_server(), result_tasks()[0])
    for name, arguments in (
        ("list_models", {}),
        ("get_model_results", {"model_hash": "different"}),
        ("get_model_results", {"model_hash": "result-example", "sections": "prediction_window"}),
    ):
        _, error = await dispatch(name, arguments)
        assert error
    assert dispatch.read_attempts == dispatch.unauthorised_read_attempts == 3
    assert dispatch.actual_reads == dispatch.unauthorised_reads == 0
    await dispatch(
        "get_model_results", {"model_hash": "result-example", "sections": "channel_summary"}
    )
    assert dispatch.actual_reads == 1
    assert dispatch.calls[-1]["actual_read"]
    assert dispatch.calls[-1]["result"]["results"]["channel_summary"]
