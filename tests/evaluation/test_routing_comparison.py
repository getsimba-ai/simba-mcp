"""Existing CLI's paired routing and continuation paths, with synthetic transports."""

import hashlib
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest

from simba_mcp.api_client import SimbaAPIClient
from simba_mcp.evaluation.experiments import source_fingerprint
from simba_mcp.evaluation.hosts import __main__ as command
from simba_mcp.evaluation.hosts import xai
from simba_mcp.evaluation.hosts.scenarios import tasks


@pytest.fixture
def anyio_backend():
    return "asyncio"


def arguments(tmp_path):
    return SimpleNamespace(
        output=tmp_path / "comparison.json",
        cap_usd=1,
        prior_usd=0,
        samples=2,
        mode="eager",
        case=None,
        model=command.GROK,
        workflow_suite="rlc01",
        case_order_seed=42,
        routing_comparison=True,
        routing_backend_url="https://example.invalid",
        routing_input_rate=0.1,
    )


@pytest.fixture
def synthetic(monkeypatch):
    task, prompt, expected = tasks()[0]
    submitted, sessions = [], []

    @asynccontextmanager
    async def host_client(_):
        yield object()

    @asynccontextmanager
    async def backend_client(url, key):
        def handler(request):
            submitted.append(request)
            return httpx.Response(
                200,
                json={
                    "schema_version": 1,
                    "routing_version": "workflow-v1",
                    "outcome": "recommended",
                    "workflow": "results",
                    "confidence": 0.96,
                    "model": "gpt-6-luna",
                    "input_tokens": 100,
                },
            )

        client = SimbaAPIClient(url, key)
        client._client = httpx.AsyncClient(
            base_url=url, headers=client._headers, transport=httpx.MockTransport(handler)
        )
        try:
            yield client
        finally:
            await client.close()

    def calibrate(*_, **__):
        # Mechanical harness fixture only; never independent grader qualification.
        return {"passed": True, "version": "synthetic-test-calibration"}

    async def session(_, tools, _prompt, dispatch, budget, checkpoint, **__):
        names = {tool["name"] for tool in tools}
        sessions.append(names)
        reservation = budget.reserve({"model": command.GROK, "max_output_tokens": 100})
        cost = budget.settle(
            {"input_tokens": 10, "output_tokens": 1, "cost_in_usd_ticks": 10000}, reservation
        )
        record = {
            "responses": [{"usage": {"input_tokens": 10, "output_tokens": 1}}],
            "cost_usd": cost,
            "calls": [],
            "stop": "end_turn",
            "seconds": 1,
        }
        checkpoint(record)
        if "recommend_workflow" in names:
            await dispatch("recommend_workflow", {"request": "Explain ROI"})
        for step in task.steps:
            await dispatch(step.tool, step.arguments)
        record["final_text"] = json.dumps(expected)
        checkpoint(record)
        return record

    monkeypatch.setenv("XAI_API_KEY", "synthetic-main-agent")
    monkeypatch.setenv("SIMBA_ROUTING_EVAL_API_KEY", "synthetic-backend")
    monkeypatch.setattr(command, "rlc_tasks", lambda: [(task, prompt, expected)])
    monkeypatch.setattr(command, "calibrate", calibrate)
    monkeypatch.setattr(command, "routing_backend_client", backend_client)
    monkeypatch.setattr(xai, "client", host_client)
    monkeypatch.setattr(xai, "session", session)
    return sessions, submitted, session


@pytest.mark.anyio
async def test_two_arms_share_domain_catalogue_and_include_selector_cost(tmp_path, synthetic):
    args = arguments(tmp_path)
    await command.run(args)
    report = json.loads(args.output.read_text())
    sessions, submitted, _ = synthetic
    assert len(sessions) == 4 and len(submitted) == 2
    assert sessions[0] == sessions[1] - {"recommend_workflow"}
    assert [row["view"] for row in report["trials"]] == [
        "baseline",
        "candidate",
        "candidate",
        "baseline",
    ]
    assert [row["complete_task_usage"]["total_input_tokens"] for row in report["trials"]] == [
        10,
        110,
        110,
        10,
    ]
    assert report["budget"]["charged"] == pytest.approx(0.000024)
    assert report["assessment"]["accepted"] is False
    assert report["routing_measurements"]["status"] == "descriptive_only"
    assert report["routing_measurements"]["paired"]["total_input_tokens"]["estimate"] == -10
    assert report["experiment_inputs"]["purpose"] == "model_selection_validation"
    assert "synthetic-backend" not in args.output.read_text()


@pytest.mark.anyio
async def test_routing_continuation_keeps_billed_failure_and_only_runs_unfinished_trials(
    tmp_path, monkeypatch, synthetic
):
    args = arguments(tmp_path)
    sessions, submitted, original_session = synthetic

    async def interrupted(*call_args, **kwargs):
        if len(sessions) == 1:
            budget, checkpoint = call_args[4:6]
            budget.reserve_decision({"model": "gpt-6-luna", "input": "Explain ROI"}, input_rate=0.1)
            checkpoint({"responses": [], "stop": "session_error", "cost_usd": 0})
            raise RuntimeError("synthetic interrupted request with unknown charge")
        return await original_session(*call_args, **kwargs)

    monkeypatch.setattr(xai, "session", interrupted)
    with pytest.raises(RuntimeError, match="interrupted"):
        await command.run(args)
    original = args.output.read_bytes()
    previous = json.loads(original)
    transition = tmp_path / "transition.json"
    transition.write_text(
        json.dumps(
            {
                "verified": True,
                "rationale": "Synthetic unchanged-source fixture",
                "previous_report_sha256": hashlib.sha256(original).hexdigest(),
                "previous_source_sha256": previous["frozen_experiment"]["source_sha256"],
                "current_source_sha256": source_fingerprint(),
            }
        )
    )
    args.continue_from = args.output
    args.continuation_review = transition
    args.output = tmp_path / "continued.json"
    args.prior_usd = sum(previous["budget"][key] for key in ("prior", "charged", "reserved"))
    monkeypatch.setattr(xai, "session", original_session)
    paid_so_far = args.prior_usd
    args.prior_usd = 0
    with pytest.raises(ValueError, match="lost prior spend"):
        await command.run(args)
    assert len(sessions) == 1 and not submitted and not args.output.exists()
    args.prior_usd = paid_so_far
    await command.run(args)
    resumed = json.loads(args.output.read_text())
    assert len(sessions) == 4 and len(resumed["trials"]) == 3
    assert args.prior_usd == pytest.approx(0.000801)
    assert args.continue_from.read_bytes() == original
    assert resumed["budget"]["prior"] == args.prior_usd
    assert len(submitted) == 2
    # This file alone omits earlier completed rows; do not report a subset saving.
    assert resumed["routing_measurements"]["status"] == "incomplete"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change",
    [
        {"routing_input_rate": 0.09},
        {"case_order_seed": None},
        {"routing_backend_url": "https://user:secret@example.invalid"},
        {"routing_backend_url": "http://example.invalid"},
        {"results_model_diagnostic": True},
    ],
)
async def test_invalid_protocol_fails_before_provider_or_output(tmp_path, synthetic, change):
    args = arguments(tmp_path)
    vars(args).update(change)
    with pytest.raises(ValueError):
        await command.run(args)
    assert not args.output.exists() and not synthetic[0] and not synthetic[1]
