"""Tiny public synthetic packets, never final held-out answers."""

import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from simba_mcp.evaluation.contracts import Case
from simba_mcp.evaluation.hosts import __main__ as command
from simba_mcp.evaluation.hosts import xai
from simba_mcp.evaluation.hosts.result_selection import ResultTask
from simba_mcp.evaluation.hosts.workflow_packet import load_workflow_packet


@pytest.fixture
def anyio_backend():
    return "asyncio"


def document():
    return {
        "schema_version": 1,
        "packet_id": "synthetic-loader-test",
        "synthetic_only": True,
        "tasks": [
            {
                "kind": "workflow",
                "prompt": "Read synthetic status. Return status as JSON.",
                "expected": {"status": "complete"},
                "contract": {
                    "id": "packet_status",
                    "purpose": "Loader test",
                    "steps": [
                        {
                            "tool": "get_model_status",
                            "arguments": {"model_hash": "synthetic"},
                            "exchanges": [
                                {
                                    "method": "GET",
                                    "path": "/api/v1/models/synthetic/status",
                                    "response": {"status": "complete"},
                                }
                            ],
                            "expected": {"status": "complete"},
                        }
                    ],
                },
            }
        ],
    }


def write(tmp_path, value):
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_strict_packet_freezes_full_contract_and_exact_bytes(tmp_path):
    path = write(tmp_path, document())
    packet = load_workflow_packet(path)
    task, prompt, expected = packet.triples()[0]
    assert isinstance(task, Case)
    assert task.steps[0].tool == "get_model_status"
    assert expected == {"status": "complete"}
    assert prompt == document()["tasks"][0]["prompt"]
    assert packet.freeze()["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert packet.freeze()["document"]["tasks"][0]["contract"]["steps"][0]["exchanges"]
    assert packet.freeze()["acceptance"] is False
    packet.verify()
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="changed"):
        packet.verify()


def test_result_contract_reuses_existing_task_without_default_fixture(tmp_path):
    data = document()
    data["tasks"] = [
        {
            "kind": "result",
            "prompt": "Read saved synthetic results.",
            "expected": {"x": 1},
            "contract": {
                "id": "packet_result",
                "required_sections": ["channel_summary"],
                "fixture": {"model_hash": "synthetic", "results": {"channel_summary": [{"x": 1}]}},
                "evidence_options": [["channel_summary"]],
                "allowed_result_sections": ["channel_summary"],
            },
        }
    ]
    task = load_workflow_packet(write(tmp_path, data)).triples()[0][0]
    assert isinstance(task, ResultTask)
    assert task.required_sections == frozenset({"channel_summary"})
    assert task.fixture == data["tasks"][0]["contract"]["fixture"]
    assert task.allowed_result_sections == task.required_sections
    del data["tasks"][0]["contract"]["fixture"]
    with pytest.raises(ValueError):
        load_workflow_packet(write(tmp_path, data))


@pytest.mark.parametrize(
    "mutation",
    ["kind", "extra", "wrongtype", "duplicate", "nonsynthetic", "missingcontract", "boolversion"],
)
def test_reject_invalid_packets(tmp_path, mutation):
    data = document()
    if mutation == "kind":
        data["tasks"][0]["kind"] = "python"
    if mutation == "extra":
        data["tasks"][0]["contract"]["module"] = "arbitrary.module"
    if mutation == "wrongtype":
        data["tasks"][0]["contract"]["steps"][0]["is_error"] = "false"
    if mutation == "duplicate":
        data["tasks"].append(deepcopy(data["tasks"][0]))
    if mutation == "nonsynthetic":
        data["synthetic_only"] = False
    if mutation == "missingcontract":
        del data["tasks"][0]["contract"]
    if mutation == "boolversion":
        data["schema_version"] = True
    with pytest.raises(ValueError):
        load_workflow_packet(write(tmp_path, data))


@pytest.mark.parametrize("raw", ['{"schema_version":1,"schema_version":1}', '{"x":NaN}'])
def test_duplicate_json_keys_and_nonfinite_rejected(tmp_path, raw):
    path = tmp_path / "packet.json"
    path.write_text(raw)
    with pytest.raises(ValueError):
        load_workflow_packet(path)


@pytest.mark.anyio
@pytest.mark.parametrize("mutate", [False, True])
async def test_cli_freezes_packet_and_rejects_mutation_at_checkpoint(tmp_path, monkeypatch, mutate):
    path = write(tmp_path, document())
    args = SimpleNamespace(
        output=tmp_path / "report.json",
        cap_usd=2,
        prior_usd=0,
        samples=1,
        mode="eager",
        case=None,
        workflow_suite="rlc01",
        workflow_packet=path,
        model="grok-4.7",
        reasoning_effort="low",
    )
    calls = []

    async def session(*args, **kwargs):
        calls.append(True)
        if mutate:
            path.write_text(path.read_text() + " ")
        record = {
            "final_text": '{"status":"complete"}',
            "cost_usd": 0,
            "calls": [],
            "stop": "end_turn",
        }
        args[5](record)
        return record

    monkeypatch.setenv("XAI_API_KEY", "synthetic-never-sent")
    monkeypatch.setattr(xai, "session", session)
    if mutate:
        with pytest.raises(ValueError, match="packet changed"):
            await command.run(args)
    else:
        await command.run(args)
    report = json.loads(args.output.read_text())
    frozen = report["configuration"]["workflow_packet"]
    assert frozen["document"]["packet_id"] == "synthetic-loader-test"
    assert report["experiment_inputs"]["configuration"]["workflow_packet"] == frozen
    assert report["assessment"]["accepted"] is False
    assert len(calls) == 1


@pytest.mark.anyio
async def test_packet_cannot_be_combined_with_historical_mode(tmp_path):
    args = SimpleNamespace(
        output=tmp_path / "report.json",
        cap_usd=2,
        prior_usd=0,
        samples=1,
        mode="eager",
        case=None,
        workflow_packet=write(tmp_path, document()),
    )
    with pytest.raises(ValueError, match="prospective RLC"):
        await command.run(args)
    assert not args.output.exists()


def test_packet_read_has_byte_ceiling(tmp_path, monkeypatch):
    from simba_mcp.evaluation.hosts import workflow_packet

    monkeypatch.setattr(workflow_packet, "MAX_PACKET_BYTES", 10)
    with pytest.raises(ValueError, match="byte limit"):
        load_workflow_packet(write(tmp_path, document()))


@pytest.mark.parametrize(
    "window",
    [
        {"unexpected": True},
        {"start": "not-a-date"},
        {"start": "2026-02-30"},
        {"start": "2026-02-02", "end": "2026-01-01"},
        {"granularity": "year"},
        {"start": 123},
    ],
)
@pytest.mark.parametrize("window_field", ["evidence_window", "section_windows"])
def test_result_windows_reject_before_execution(tmp_path, window, window_field):
    data = document()
    contract = {
        "id": "packet_result",
        "required_sections": ["channel_summary"],
        "fixture": {"model_hash": "synthetic", "results": {}},
    }
    contract[window_field] = (
        {"channel_summary": window} if window_field == "section_windows" else window
    )
    data["tasks"] = [
        {
            "kind": "result",
            "prompt": "Read synthetic results",
            "expected": {"x": 1},
            "contract": contract,
        }
    ]
    with pytest.raises(ValueError):
        load_workflow_packet(write(tmp_path, data))


@pytest.mark.parametrize("identity", [None, "", "   ", 12, False])
def test_result_identity_cannot_fall_back_to_default(tmp_path, identity):
    data = document()
    data["tasks"] = [
        {
            "kind": "result",
            "prompt": "Read synthetic results",
            "expected": {"x": 1},
            "contract": {
                "id": "packet_result",
                "required_sections": ["channel_summary"],
                "fixture": {"model_hash": identity, "results": {}},
            },
        }
    ]
    with pytest.raises(ValueError, match="model_hash"):
        load_workflow_packet(write(tmp_path, data))


def test_overflow_number_is_rejected_during_loading(tmp_path):
    path = tmp_path / "packet.json"
    path.write_text('{"x":1e999}')
    with pytest.raises(ValueError, match="Non-finite"):
        load_workflow_packet(path)


def test_valid_windows_preserve_canonical_argument_types(tmp_path):
    data = document()
    window = {"start": "2026-01-01", "end": "2026-01-31", "granularity": "month"}
    data["tasks"] = [
        {
            "kind": "result",
            "prompt": "Read synthetic results",
            "expected": {"x": 1},
            "contract": {
                "id": "packet_result",
                "required_sections": ["channel_summary"],
                "fixture": {"model_hash": "synthetic", "results": {}},
                "evidence_window": window,
                "section_windows": {"channel_summary": window},
            },
        }
    ]
    task = load_workflow_packet(write(tmp_path, data)).triples()[0][0]
    assert task.evidence_window == window
    assert task.section_windows == {"channel_summary": window}


@pytest.mark.anyio
async def test_prospective_campaign_snapshot_accepts_declared_window_only():
    from simba_mcp.evaluation.hosts.scenarios import SyntheticDispatch
    from simba_mcp.server import create_server

    packet = load_workflow_packet("docs/evaluations/packets/routing-task-selection-v3.json")
    case = next(task for task, _, _ in packet.triples() if task.id == "role_campaign_facts")
    for arguments in (
        {"model_hash": "model-example"},
        {"model_hash": "model-example", "start": "2026-09-01", "end": "2026-09-28"},
    ):
        dispatch = SyntheticDispatch(create_server(profile="full"), case)
        result, error = await dispatch("list_campaigns", arguments)
        assert not error and dispatch.errors == 0
        assert result["campaigns"][0]["campaign_id"] == "campaign-example"
        repeated, error = await dispatch("list_campaigns", arguments)
        assert not error and dispatch.errors == 0
        assert repeated == result
    dispatch = SyntheticDispatch(create_server(profile="full"), case)
    _, error = await dispatch(
        "list_campaigns",
        {"model_hash": "model-example", "start": "2026-08-01", "end": "2026-09-28"},
    )
    assert error and dispatch.errors == 1
