"""Existing CLI's paired routing and continuation paths, with synthetic transports."""

import hashlib
import json
import sys
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest

from simba_mcp.api_client import SimbaAPIClient
from simba_mcp.evaluation.experiments import source_fingerprint
from simba_mcp.evaluation.hosts import __main__ as command
from simba_mcp.evaluation.hosts import xai
from simba_mcp.evaluation.hosts.routing_report import main as campaign_main
from simba_mcp.evaluation.hosts.routing_report import routing_campaign_report
from simba_mcp.evaluation.hosts.scenarios import tasks


@pytest.fixture
def anyio_backend():
    return "asyncio"


def arguments(tmp_path):
    task, prompt, expected = tasks()[0]
    packet = tmp_path / "packet.json"
    packet.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "packet_id": "mechanical-test-packet",
                "synthetic_only": True,
                "author": "synthetic-test-author",
                "provenance": "Mechanical harness fixture, not actual independent review",
                "split": "selection_validation",
                "tasks": [
                    {
                        "kind": "workflow",
                        "family": "results",
                        "prompt": prompt,
                        "expected": expected,
                        "contract": task.model_dump(mode="json"),
                    }
                ],
            }
        )
    )
    review = tmp_path / "review.json"
    artifact = tmp_path / "audit.json"
    artifact.write_text('{"mechanical_fixture_only": true}')
    review.write_text(
        json.dumps(
            {
                "passed": True,
                "reviewer": "synthetic-test-reviewer",
                "review_type": "independent_agent",
                "packet_sha256": hashlib.sha256(packet.read_bytes()).hexdigest(),
                "source_sha256": source_fingerprint(),
                "review_artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "grader_version": 20,
                "rationale": "Mechanical harness only, not qualification evidence",
            }
        )
    )
    return SimpleNamespace(
        workflow_packet=packet,
        workflow_review=review,
        workflow_review_artifact=artifact,
        grader_version=20,
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
        reservation = budget.reserve(
            {
                "model": budget.model,
                "max_output_tokens" if budget.model == command.GROK else "max_tokens": 100,
            }
        )
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
async def test_two_arms_share_domain_catalogue_and_include_selector_cost(
    tmp_path, synthetic, monkeypatch
):
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
    campaign = routing_campaign_report([args.output])
    assert campaign["status"] == "descriptive_only"
    assert campaign["campaign"]["attempt_count"] == 4
    assert campaign["campaign"]["cumulative_spend_and_reservations_usd"] == pytest.approx(0.000024)
    archived = args.output.read_bytes()
    campaign_path = tmp_path / "campaign.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["routing_report", "--report", str(args.output), "--output", str(campaign_path)],
    )
    campaign_main()
    assert json.loads(campaign_path.read_text()) == campaign
    with pytest.raises(ValueError, match="overwrite"):
        campaign_main()
    assert args.output.read_bytes() == archived and len(submitted) == 2


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
    campaign = routing_campaign_report([args.continue_from, args.output])
    assert campaign["campaign"]["attempt_count"] == 5
    assert campaign["campaign"]["restarted_trials"] == 1
    assert campaign["campaign"]["attempt_outcomes"] == {"pass": 4, "execution_error": 1}
    assert campaign["arms"]["baseline"]["recorded_trials"] == 2
    assert campaign["arms"]["candidate"]["recorded_trials"] == 2
    assert campaign["status"] == "incomplete" and campaign["paired"] is None
    assert campaign["campaign"]["cumulative_spend_and_reservations_usd"] > args.prior_usd
    with pytest.raises(ValueError, match="original report"):
        routing_campaign_report([args.output])
    for fault in ("prior", "chain", "completed"):
        changed = json.loads(args.output.read_text())
        if fault == "prior":
            changed["budget"]["prior"] = 0
        elif fault == "chain":
            changed["configuration"]["continuation"]["previous_report_sha256"] = "0" * 64
        else:
            changed["configuration"]["continuation"]["completed_trials"] = []
        # Bind modified configuration correctly, so lineage checks must reject it.
        from simba_mcp.evaluation.experiments import fingerprint

        changed["experiment_inputs"]["configuration"] = changed["configuration"]
        changed["frozen_experiment"]["inputs_sha256"] = fingerprint(changed["experiment_inputs"])
        tampered = tmp_path / (fault + ".json")
        tampered.write_text(json.dumps(changed))
        with pytest.raises(ValueError, match="continuation chain|lost spending"):
            routing_campaign_report([args.continue_from, tampered])


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change",
    [
        {"routing_input_rate": 0.09},
        {"case_order_seed": None},
        {"routing_backend_url": "https://user:secret@example.invalid"},
        {"routing_backend_url": "http://example.invalid"},
        {"results_model_diagnostic": True},
        {"workflow_review": None},
        {"workflow_packet": None},
        {"workflow_review_artifact": None},
        {"grader_version": 17},
    ],
)
async def test_invalid_protocol_fails_before_provider_or_output(tmp_path, synthetic, change):
    args = arguments(tmp_path)
    vars(args).update(change)
    with pytest.raises(ValueError):
        await command.run(args)
    assert not args.output.exists() and not synthetic[0] and not synthetic[1]


@pytest.mark.anyio
async def test_audit_bytes_must_match_review_before_provider(tmp_path, synthetic):
    args = arguments(tmp_path)
    args.workflow_review_artifact.write_text('{"changed": true}')
    with pytest.raises(ValueError):
        await command.run(args)
    assert not args.output.exists() and not synthetic[0] and not synthetic[1]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "field,value",
    [
        ("passed", False),
        ("reviewer", "synthetic-test-author"),
        ("packet_sha256", "0" * 64),
        ("source_sha256", "0" * 64),
        ("grader_version", 19),
    ],
)
async def test_review_mismatch_stops_before_provider(tmp_path, synthetic, field, value):
    args = arguments(tmp_path)
    review = json.loads(args.workflow_review.read_text())
    review[field] = value
    args.workflow_review.write_text(json.dumps(review))
    with pytest.raises(ValueError):
        await command.run(args)
    assert not args.output.exists() and not synthetic[0] and not synthetic[1]


@pytest.mark.anyio
async def test_explicit_anthropic_model_is_same_in_both_routing_arms(
    tmp_path, synthetic, monkeypatch
):
    args = arguments(tmp_path)
    args.model = command.MODEL
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-main-agent")
    monkeypatch.setattr(command, "client", xai.client)
    monkeypatch.setattr(command, "session", xai.session)
    await command.run(args)
    report = json.loads(args.output.read_text())
    assert report["configuration"]["routing_comparison"]["version"] == "hosted-routing-v4"
    assert report["budget"]["model"] == command.MODEL
    assert len(synthetic[0]) == 4
    assert report["budget"]["charged"] == pytest.approx(0.00008)


@pytest.mark.anyio
@pytest.mark.parametrize("version, expected_outcome", [(20, "fail"), (21, "review")])
async def test_sufficient_workflow_facts_with_extra_claim_require_review(
    tmp_path, synthetic, monkeypatch, version, expected_outcome
):
    args = arguments(tmp_path)
    args.grader_version = version
    review = json.loads(args.workflow_review.read_text())
    review["grader_version"] = version
    args.workflow_review.write_text(json.dumps(review))
    original_session = synthetic[2]

    async def with_metadata(provider, definitions, prompt, dispatch, budget, checkpoint, **kwargs):
        record = await original_session(
            provider, definitions, prompt, dispatch, budget, checkpoint, **kwargs
        )
        facts = json.loads(record["final_text"])
        record["final_text"] = json.dumps({**facts, "additional_claim": "needs independent review"})
        checkpoint(record)
        return record

    monkeypatch.setattr(xai, "session", with_metadata)
    await command.run(args)
    report = json.loads(args.output.read_text())
    assert all(t["fact_verdict"] == "pass" for t in report["trials"])
    assert all(t["outcome"] == expected_outcome for t in report["trials"])
    assert all(t["claim_review_required"] for t in report["trials"])
    assert all(not t["passed"] for t in report["trials"])


@pytest.mark.anyio
async def test_campaign_retains_terminal_turn_limit_failure(tmp_path, synthetic, monkeypatch):
    args = arguments(tmp_path)
    original_session = synthetic[2]

    async def turn_limited(*positional, **kwargs):
        record = await original_session(*positional, **kwargs)
        record.pop("final_text")
        record["stop"] = "turn_limit"
        return record

    monkeypatch.setattr(xai, "session", turn_limited)
    await command.run(args)
    campaign = routing_campaign_report([args.output])
    assert campaign["campaign"]["attempt_count"] == 4
    assert campaign["campaign"]["attempt_outcomes"] == {"fail": 4}
    assert campaign["arms"]["baseline"]["outcomes"]["fail"] == 2
    bad = json.loads(args.output.read_text())
    bad["trials"][0]["session"]["stop"] = "unrecognised"
    tampered = tmp_path / "unsupported-terminal.json"
    tampered.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="incomplete terminal evidence"):
        routing_campaign_report([tampered])
