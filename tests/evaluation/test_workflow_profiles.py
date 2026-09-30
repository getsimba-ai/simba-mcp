"""Existing catalogue profiles remain explicit and frozen in RLC experiments."""

import json
from types import SimpleNamespace

import pytest

from simba_mcp.evaluation.hosts.models import GROK
from simba_mcp.profiles import PROFILES


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("profile", ["full", "reviewer"])
async def test_profile_registration_and_report(tmp_path, monkeypatch, profile):
    from simba_mcp.evaluation.hosts import __main__ as command
    from simba_mcp.evaluation.hosts import xai

    async def fake_session(client, tools, prompt, dispatch, budget, checkpoint, **kwargs):
        names = {t["name"] for t in tools}
        if profile == "reviewer":
            assert names == PROFILES["reviewer"]
            assert "run_optimizer" not in names
        else:
            assert "run_optimizer" in names
        for step in dispatch.case.steps:
            await dispatch(step.tool, step.arguments)
        return {
            "final_text": json.dumps(
                {
                    "metric": "holdout",
                    "status": "not_evaluated",
                    "basis": {"reason": "not_collected"},
                }
            ),
            "stop": "end_turn",
        }

    monkeypatch.setenv("XAI_API_KEY", "synthetic")
    monkeypatch.setattr(xai, "session", fake_session)
    output = tmp_path / "report.json"
    await command.run(
        SimpleNamespace(
            output=output,
            cap_usd=1,
            prior_usd=0,
            samples=1,
            case="study_review",
            mode="eager",
            model=GROK,
            reasoning_effort="low",
            workflow_suite="rlc01",
            tool_profile=profile,
        )
    )
    report = json.loads(output.read_text())
    assert report["configuration"]["tool_profile"] == profile
    assert report["trials"][0]["view"] == profile
    assert report["trials"][0]["passed"]
    assert report["assessment"]["accepted"] is False


@pytest.mark.anyio
async def test_profile_cannot_change_historical_experiment(tmp_path):
    from simba_mcp.evaluation.hosts.__main__ import run

    with pytest.raises(ValueError, match="prospective RLC"):
        await run(
            SimpleNamespace(
                output=tmp_path / "unused.json",
                cap_usd=0,
                prior_usd=0,
                samples=1,
                case=None,
                mode="eager",
                model=GROK,
                tool_profile="reviewer",
            )
        )
