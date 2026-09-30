import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from simba_mcp.evaluation.experiments import source_fingerprint
from simba_mcp.evaluation.hosts import __main__ as command
from simba_mcp.guidance import read_guidance


@pytest.fixture
def anyio_backend():
    return "asyncio"


def arguments(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                s: read_guidance("results", s)
                for s in ("entrypoint", "interpretation", "tool-reference")
            }
        )
    )
    return SimpleNamespace(
        output=tmp_path / "original.json",
        cap_usd=2,
        prior_usd=0,
        samples=2,
        mode="eager",
        case="v3_channel_comparison",
        results_robust=True,
        results_acceptance=True,
        results_acceptance_packet="v3",
        results_baseline=baseline,
        case_order_seed=42,
        case_review={"verified": True, "guidance_unchanged": True},
    )


@pytest.mark.anyio
async def test_local_rename_retry_does_not_repeat_provider_session(tmp_path, monkeypatch):
    args = arguments(tmp_path)
    calls = []
    failures = []
    original_replace = Path.replace

    def transient_replace(path, target):
        if target == args.output and len(failures) < 2:
            failures.append(True)
            raise PermissionError("Synthetic reader lock")
        return original_replace(path, target)

    async def session(*_args, **_kwargs):
        calls.append(True)
        return {"final_text": "{}", "cost_usd": 0, "calls": [], "stop": "end_turn"}

    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-key")
    monkeypatch.setattr(command, "session", session)
    monkeypatch.setattr(Path, "replace", transient_replace)
    monkeypatch.setattr(command.time, "sleep", lambda _: None)
    await command.run(args)
    assert len(failures) == 2 and len(calls) == 4
    assert json.loads(args.output.read_text())["status"] == "complete"


@pytest.mark.anyio
async def test_permanent_rename_failure_preserves_temporary_ledger_without_provider(
    tmp_path, monkeypatch
):
    args = arguments(tmp_path)
    attempts = []

    def locked(path, target):
        attempts.append(True)
        raise PermissionError("Synthetic persistent lock")

    def forbidden_provider(*_):
        pytest.fail("Provider must not open before the initial checkpoint is durable")

    monkeypatch.setattr(Path, "replace", locked)
    monkeypatch.setattr(command.time, "sleep", lambda _: None)
    monkeypatch.setattr(command, "client", forbidden_provider)
    with pytest.raises(PermissionError):
        await command.run(args)
    assert len(attempts) == 10 and not args.output.exists()
    pending = json.loads(args.output.with_suffix(".tmp").read_text())
    assert pending["budget"]["charged"] == pending["budget"]["reserved"] == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mutation",
    [
        None,
        "lost_spend",
        "changed_model",
        "changed_prompt",
        "changed_review",
        "changed_cap",
        "unreviewed_source",
        "incomplete_terminal",
    ],
)
async def test_continuation_preserves_completed_failures_and_rejects_drift(
    tmp_path, monkeypatch, mutation
):
    args = arguments(tmp_path)
    calls = []

    async def interrupted(*session_args, **_kwargs):
        calls.append(True)
        if len(calls) == 2:
            raise RuntimeError("Synthetic interruption")
        session_args[4].charged += 0.25
        record = {"final_text": "{}", "cost_usd": 0.25, "calls": [], "stop": "end_turn"}
        session_args[5](record)
        return record

    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-key")
    monkeypatch.setattr(command, "session", interrupted)
    with pytest.raises(RuntimeError, match="Synthetic interruption"):
        await command.run(args)
    original_bytes = args.output.read_bytes()
    old = json.loads(original_bytes)
    assert old["status"] == "stopped" and len(old["trials"]) == 2
    assert old["trials"][0]["passed"] is False
    args.continue_from = args.output
    args.output = tmp_path / "continuation.json"
    args.prior_usd = 0.25
    transition = {
        "verified": True,
        "previous_report_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "rationale": "Synthetic no-source-change continuation test",
        "previous_source_sha256": old["frozen_experiment"]["source_sha256"],
        "current_source_sha256": source_fingerprint(),
    }
    args.continuation_review = tmp_path / "review.json"
    args.continuation_review.write_text(json.dumps(transition))
    if mutation == "lost_spend":
        args.prior_usd = 0
    elif mutation == "changed_model":
        args.reasoning_effort = "low"
        args.model = "grok-4.7"
    elif mutation == "changed_prompt":
        args.results_prompt = "paraphrase"
    elif mutation == "changed_review":
        args.case_review = {**args.case_review, "new_unreviewed_assertion": True}
    elif mutation == "changed_cap":
        args.cap_usd = 3
    elif mutation == "unreviewed_source":
        transition["current_source_sha256"] = "0" * 64
        args.continuation_review.write_text(json.dumps(transition))
    elif mutation == "incomplete_terminal":
        old["trials"][0].pop("outcome")
        original_bytes = json.dumps(old).encode()
        args.continue_from.write_bytes(original_bytes)
        transition["previous_report_sha256"] = hashlib.sha256(original_bytes).hexdigest()
        args.continuation_review.write_text(json.dumps(transition))
    resumed_calls = []

    async def resumed(*_args, **_kwargs):
        resumed_calls.append(True)
        record = {"final_text": "{}", "cost_usd": 0, "calls": [], "stop": "end_turn"}
        _args[5](record)
        return record

    monkeypatch.setattr(command, "session", resumed)
    if mutation:
        with pytest.raises(ValueError, match="Continuation"):
            await command.run(args)
        assert not resumed_calls and not args.output.exists()
    else:
        await command.run(args)
        result = json.loads(args.output.read_text())
        assert len(resumed_calls) == len(result["trials"]) == 3
        keys = lambda rows: {(r["case"], r["view"], r["repetition"]) for r in rows}
        assert not keys(result["trials"]) & keys(old["trials"][:1])
        assert result["budget"]["prior"] == 0.25
        assert not result["assessment"]["accepted"]
    assert args.continue_from.read_bytes() == original_bytes
