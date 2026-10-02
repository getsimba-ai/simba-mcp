"""Opt-in canonical identity semantics preserve grader 17 and frozen continuation."""

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from simba_mcp.evaluation.hosts import __main__ as command
from simba_mcp.evaluation.hosts import result_selection, xai
from simba_mcp.evaluation.hosts.result_calibration import calibrate
from simba_mcp.evaluation.hosts.result_grading import semantic_facts
from simba_mcp.evaluation.hosts.result_rlc_tasks import rlc_development_tasks
from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch
from simba_mcp.evaluation.result_cases import saved_results
from simba_mcp.server import create_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


def identity_task():
    task = next(t for t in rlc_development_tasks() if t.id == "result_roi")
    fixture = saved_results()
    row = next(r for r in fixture["results"]["channel_map"] if r["activity_column"] == task.channel)
    row["channel"] = "Paid Discovery"
    return replace(task, id="prospective_identity", fixture=fixture)


def test_default_remains_historical_and_new_labels_are_explicit():
    task = identity_task()
    facts = {**task.expected, "channel": "Paid Discovery"}
    assert not semantic_facts(task, facts, {"channel_map"})
    assert not semantic_facts(task, facts, {"channel_map"}, grader_version=17)
    assert semantic_facts(task, facts, {"channel_map"}, grader_version=18)
    assert calibrate() == calibrate(grader_version=17)
    assert calibrate()["grader_version"] == 17
    new = calibrate(grader_version=18)
    assert new["grader_version"] == 18 and new["passed"]
    assert len(new["cases"]) == len(calibrate()["cases"]) + 8


@pytest.mark.parametrize("evidence", [set(), {"channel_summary"}, {"verified_media_identity"}])
def test_mapping_evidence_is_required(evidence):
    task = identity_task()
    assert not semantic_facts(
        task, {**task.expected, "channel": "Paid Discovery"}, evidence, grader_version=18
    )


@pytest.mark.parametrize("mutation", ["wrong", "ambiguous", "duplicate", "case"])
def test_wrong_or_ambiguous_mapping_never_becomes_fuzzy_acceptance(mutation):
    task = identity_task()
    fixture = deepcopy(task.fixture)
    rows = fixture["results"]["channel_map"]
    target = next(r for r in rows if r["activity_column"] == task.channel)
    if mutation == "wrong":
        target["channel"] = "Other display"
    elif mutation == "ambiguous":
        rows.append({**target, "activity_column": "another_activity"})
    elif mutation == "duplicate":
        rows.append(dict(target))
    facts = {
        **task.expected,
        "channel": "paid discovery" if mutation == "case" else "Paid Discovery",
    }
    assert not semantic_facts(
        replace(task, fixture=fixture), facts, {"channel_map"}, grader_version=18
    )


@pytest.mark.anyio
@pytest.mark.parametrize("wrong_returned_map", [False, True])
async def test_dispatch_requires_returned_mapping_not_hidden_fixture(
    wrong_returned_map, monkeypatch
):
    task = identity_task()
    original = result_selection.run_case

    async def changed_response(case, **kwargs):
        case = case.model_copy(deep=True)
        payload = case.steps[0].exchanges[0].response
        if wrong_returned_map:
            for row in payload["results"].get("channel_map", []):
                row["channel"] = "Wrong returned identity"
        return await original(case, **kwargs)

    monkeypatch.setattr(result_selection, "run_case", changed_response)
    dispatch = ResultSelectionDispatch(create_server("compact"), task, grader_version=18)
    facts = {**task.expected, "channel": "Paid Discovery"}
    await dispatch(
        "get_model_results",
        {
            "model_hash": "result-example",
            "sections": "channel_summary",
            "start": "2025-01-01",
            "end": "2025-02-28",
        },
    )
    assert not dispatch.grade(facts)["facts"] and not dispatch.grade(facts)["required_evidence"]
    await dispatch("get_model_results", {"model_hash": "result-example", "sections": "channel_map"})
    assert dispatch.grade(facts)["facts"] is (not wrong_returned_map)
    assert dispatch.grade(facts)["required_evidence"] is (not wrong_returned_map)


@pytest.mark.anyio
@pytest.mark.parametrize("selected_version", [18, 19])
async def test_grader_version_frozen_and_continuation_cannot_switch(
    tmp_path, monkeypatch, selected_version
):
    args = SimpleNamespace(
        output=tmp_path / "original.json",
        cap_usd=2,
        prior_usd=0,
        samples=2,
        mode="eager",
        case="result_roi",
        workflow_suite="rlc01",
        model="grok-4.7",
        reasoning_effort="low",
        grader_version=selected_version,
    )
    calls = []

    async def interrupted(*values, **kwargs):
        calls.append(True)
        if len(calls) == 2:
            raise RuntimeError("Synthetic interruption")
        return {"final_text": "{}", "cost_usd": 0, "calls": [], "stop": "end_turn"}

    monkeypatch.setenv("XAI_API_KEY", "synthetic-never-sent")
    monkeypatch.setattr(xai, "session", interrupted)
    with pytest.raises(RuntimeError, match="Synthetic interruption"):
        await command.run(args)
    report = json.loads(args.output.read_text())
    assert report["configuration"]["grader_version"] == selected_version
    assert report["calibration"]["grader_version"] == selected_version
    assert report["trials"][0]["grader_version"] == selected_version
    args.continue_from = args.output
    args.output = tmp_path / "continued.json"
    args.grader_version = 17
    with pytest.raises(ValueError):
        await command.run(args)
    assert len(calls) == 2


@pytest.mark.anyio
async def test_new_grader_cannot_change_historical_mode(tmp_path):
    args = SimpleNamespace(
        output=tmp_path / "report.json", cap_usd=2, prior_usd=0, mode="eager", grader_version=18
    )
    with pytest.raises(ValueError, match="prospective"):
        await command.run(args)
    assert not args.output.exists()


def test_version18_does_not_fill_missing_identity_when_mapping_is_ambiguous():
    task = identity_task()
    fixture = deepcopy(task.fixture)
    mapping = fixture["results"]["channel_map"]
    target = next(row for row in mapping if row["activity_column"] == task.channel)
    mapping.append(dict(target))
    facts = {k: v for k, v in task.expected.items() if k != "channel"}
    assert not semantic_facts(
        replace(task, fixture=fixture), facts, {"channel_map"}, grader_version=18
    )


@pytest.mark.parametrize("version", [True, 17.0, 20, None])
def test_invalid_versions_are_rejected(version):
    with pytest.raises(ValueError, match="grader version"):
        calibrate(grader_version=version)


def test_version17_calibration_matches_pre_repair_snapshot():
    digest = hashlib.sha256(json.dumps(calibrate(), sort_keys=True).encode()).hexdigest()
    assert digest == "ee5aa61455bdabf4ab6496e780f9959e4dc2174b3f85292c8b17289c18e7d491"


def test_version18_default_aliases_do_not_fill_an_explicit_empty_fixture():
    task = next(t for t in rlc_development_tasks() if t.id == "result_roi")
    task = replace(task, fixture=None)
    facts = {**task.expected, "channel": "Search"}
    assert semantic_facts(task, facts, {"channel_map"}, grader_version=18)
    assert not semantic_facts(replace(task, fixture={}), facts, {"channel_map"}, grader_version=18)
