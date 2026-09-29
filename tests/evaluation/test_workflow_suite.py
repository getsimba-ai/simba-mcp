import json
from types import SimpleNamespace

import pytest

from simba_mcp.evaluation.hosts.result_selection import ResultTask
from simba_mcp.evaluation.hosts.scenarios import rlc_tasks


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_prospective_inventory_has_twenty_cases_and_explicit_refusal():
    suite = rlc_tasks()
    assert len(suite) == len({case.id for case, _, _ in suite}) == 20
    assert sum(isinstance(case, ResultTask) for case, _, _ in suite) == 11
    names = {case.id for case, _, _ in suite}
    assert {"rlc01_attribution_absence", "rlc01_diagnostics", "stale_revision"} <= names
    assert not {"result_diagnostics", "result_decomposition"} & names
    refusal, prompt, expected = suite[-1]
    assert refusal.steps[0].is_error
    assert "exactly one" in prompt and "Do not retry" in prompt
    assert expected == {"status_code": 412, "published": False, "retry_attempted": False}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "case_id",
    ["study_review", "cross_domain", "stale_revision", "evidence_recommendation", "result_roi"],
)
async def test_rlc_cli_dispatches_and_freezes_single_arm(tmp_path, monkeypatch, case_id):
    from simba_mcp.evaluation.hosts import __main__ as command
    from simba_mcp.evaluation.hosts import xai
    from simba_mcp.evaluation.hosts.models import GROK

    case, _, expected = next(item for item in rlc_tasks() if item[0].id == case_id)

    async def fake_session(client, tools, prompt, dispatch, budget, checkpoint, **kwargs):
        assert kwargs["session_timeout_seconds"] == 5
        if isinstance(case, ResultTask):
            await dispatch(
                "get_model_results",
                {"model_hash": "result-example", "sections": "channel_summary,channel_map"},
            )
        else:
            for step in case.steps:
                _, error = await dispatch(step.tool, step.arguments)
                assert error == step.is_error
        return {"final_text": json.dumps(expected), "stop": "end_turn"}

    monkeypatch.setattr(xai, "session", fake_session)
    monkeypatch.setenv("XAI_API_KEY", "synthetic-key")
    output = tmp_path / "report.json"
    await command.run(
        SimpleNamespace(
            output=output,
            cap_usd=1,
            prior_usd=0,
            samples=1,
            case=case_id,
            mode="eager",
            model=GROK,
            reasoning_effort="low",
            workflow_suite="rlc01",
            session_timeout_seconds=5,
        )
    )
    report = json.loads(output.read_text())
    assert report["status"] == "complete"
    assert report["configuration"]["workflow_suite"] == "rlc01"
    assert report["configuration"]["session_timeout_seconds"] == 5
    assert report["frozen_experiment"]["inputs_sha256"]
    assert len(report["trials"]) == 1
    row = report["trials"][0]
    assert row["passed"] and row["outcome"] == "pass"
    assert row["execution_trials"] and row["trajectory"]
    assert "synthetic-key" not in output.read_text()


@pytest.mark.anyio
async def test_rlc_rejects_historical_comparison_mode_before_provider(tmp_path):
    from simba_mcp.evaluation.hosts.__main__ import run

    with pytest.raises(ValueError, match="historical comparison"):
        await run(
            SimpleNamespace(
                output=tmp_path / "unused.json",
                cap_usd=0,
                prior_usd=0,
                samples=1,
                case=None,
                mode="eager",
                workflow_suite="rlc01",
                role_comparison="reviewer",
            )
        )


def test_single_sample_freeze_is_only_prospective_smoke():
    from simba_mcp.evaluation.experiments import freeze_experiment

    inputs = {
        "purpose": "development_smoke",
        "samples": 1,
        "configuration": {"workflow_suite": "rlc01"},
    }
    assert freeze_experiment(inputs, {"passed": True})
    for changed in ({"purpose": "development"}, {"configuration": {}}, {"samples": 0}):
        with pytest.raises(ValueError):
            freeze_experiment({**inputs, **changed}, {"passed": True})
