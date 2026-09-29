"""The evaluator must detect faults, not merely agree with its own fixtures."""

import asyncio
import json
import socket
from copy import deepcopy

import pytest
from pydantic import ValidationError

from simba_mcp import evaluation, telemetry
from simba_mcp.api_client import CALLER_API_KEY
from simba_mcp.evaluation_cases import cases


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("case", cases(), ids=lambda c: c.id)
async def test_public_cases_pass_without_sockets(case, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No socket allowed")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    trial = await evaluation.run_case(case)
    assert trial.passed, trial.assertions
    assert trial.unintended_writes == 0
    assert trial.backend_attempts == sum(len(s.exchanges) for s in case.steps)
    assert trial.provider_usage is None
    assert telemetry.get_sink() is None


@pytest.mark.anyio
@pytest.mark.parametrize("case", cases(), ids=lambda c: c.id)
async def test_every_case_detects_a_broken_expectation(case):
    broken = case.model_copy(deep=True)
    step = broken.steps[0]
    if step.cancelled:
        step.cancelled = False
        with pytest.raises(asyncio.CancelledError):
            await evaluation.run_case(broken)
    else:
        if step.tool_error:
            step.tool_error = "different refusal"
        else:
            step.expected = {"absent_synthetic_field": "must exist"}
        assert not (await evaluation.run_case(broken)).passed


@pytest.mark.anyio
async def test_unintended_write_and_payload_change_fail():
    case = next(c for c in cases() if c.id == "create_mmm")
    case.steps[0].arguments["sampler"]["chains"] = 4
    trial = await evaluation.run_case(case)
    assert not trial.passed
    assert trial.unintended_writes == 1


@pytest.mark.anyio
async def test_missing_evidence_cannot_be_turned_into_pass():
    case = next(c for c in cases() if c.id == "study_review")
    response = case.steps[0].exchanges[0].response
    response["evaluations"][0]["report"]["checks"][0]["status"] = "pass"
    assert not (await evaluation.run_case(case)).passed


@pytest.mark.anyio
async def test_cleanup_preserves_callers_and_external_cancellation(monkeypatch):
    case = next(c for c in cases() if c.id == "cancellation")
    token = CALLER_API_KEY.set("caller-sentinel")
    sink = lambda event: None
    try:
        with telemetry.use_sink(sink):
            await evaluation.run_case(case)
            assert CALLER_API_KEY.get() == "caller-sentinel"
            assert telemetry.get_sink() is sink

            async def cancel(*args, **kwargs):
                raise asyncio.CancelledError()

            monkeypatch.setattr(evaluation.server.mcp, "call_tool", cancel)
            with pytest.raises(asyncio.CancelledError):
                await evaluation.run_case(case)
            assert CALLER_API_KEY.get() == "caller-sentinel"
    finally:
        CALLER_API_KEY.reset(token)


def test_manifest_validation_and_exact_values():
    data = cases()[0].model_dump()
    data["unexpected"] = True
    with pytest.raises(ValidationError):
        evaluation.Case.model_validate(data)
    with pytest.raises(ValidationError):
        evaluation.Step(tool="x", arguments={}, exchanges=[], expected={})
    assert not evaluation.contains({"channel": "Search"}, {"channel": "search"})
    assert not evaluation.contains({"interval": [1, 2]}, {"interval": [2, 1]})
    assert not evaluation.contains({"value": True}, {"value": 1})


@pytest.mark.anyio
async def test_report_omits_raw_data_and_rejects_fabricated_usage():
    trial = await evaluation.run_case(cases()[0])
    data = trial.model_dump()
    assert "model-example" not in json.dumps(data)
    assert "synthetic-key" not in json.dumps(data)
    assert trial.backend_decoded_bytes > 0
    assert trial.backend_downloaded_bytes > 0
    bad = deepcopy(data)
    bad["provider_usage"] = {"input_tokens": 0}
    with pytest.raises(ValidationError):
        evaluation.Trial.model_validate(bad)
    bad = deepcopy(data)
    bad["unintended_writes"] = 1
    with pytest.raises(ValidationError):
        evaluation.Trial.model_validate(bad)
