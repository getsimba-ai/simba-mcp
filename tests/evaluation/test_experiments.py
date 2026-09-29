"""Protect experimental validity rather than rewarding a particular candidate."""

from copy import deepcopy

import pytest

from simba_mcp.evaluation import experiments
from simba_mcp.evaluation.hosts.result_calibration import calibrate
from simba_mcp.evaluation.hosts.result_grading import structured_answer_only
from simba_mcp.evaluation.hosts.result_selection import (
    ResultSelectionDispatch,
    development_tasks,
)
from simba_mcp.server import create_server


def test_calibration_has_positive_negative_and_claim_review_labels():
    report = calibrate()
    assert report["passed"]
    assert {r["expected_facts"] for r in report["cases"]} == {True, False}
    assert any(not r["expected_claims_in_scope"] for r in report["cases"])
    assert "pending" in report["label_review"]


def test_calibration_detects_broken_grader(monkeypatch):
    from simba_mcp.evaluation.hosts import result_calibration

    monkeypatch.setattr(result_calibration, "semantic_facts", lambda *_: True)
    assert not result_calibration.calibrate()["passed"]


def test_freeze_rejects_changed_inputs_source_and_failed_calibration(monkeypatch):
    monkeypatch.setattr(experiments, "source_fingerprint", lambda: "original")
    inputs = {"purpose": "development", "samples": 2, "guidance": "original"}
    calibration = calibrate()
    frozen = experiments.freeze_experiment(inputs, calibration)
    experiments.verify_experiment(frozen, inputs, calibration)
    with pytest.raises(ValueError, match="changed"):
        experiments.verify_experiment(frozen, {**inputs, "guidance": "tuned"}, calibration)
    monkeypatch.setattr(experiments, "source_fingerprint", lambda: "changed")
    with pytest.raises(ValueError, match="changed"):
        experiments.verify_experiment(frozen, inputs, calibration)
    with pytest.raises(ValueError, match="calibration"):
        experiments.freeze_experiment(inputs, {"passed": False})
    with pytest.raises(ValueError, match="acceptance"):
        experiments.freeze_experiment({**inputs, "purpose": "acceptance"}, calibration)


def rows_for(families, samples=2):
    return [
        {
            "case": case,
            "view": arm,
            "repetition": rep,
            "passed": True,
            "session": {"cost_usd": 1.0 if arm == "baseline" else 0.8},
            "assertions": {
                k: True
                for k in (
                    "facts",
                    "claims_in_scope",
                    "required_evidence",
                    "no_errors",
                    "no_unintended_writes",
                    "executed",
                    "no_unreviewed_prose",
                )
            },
        }
        for case in families
        for rep in range(samples)
        for arm in ("baseline", "candidate")
    ]


def test_repetitions_and_related_questions_do_not_inflate_family_count():
    families = {"a": "one", "a_paraphrase": "one", "b": "two"}
    result = experiments.assess_comparison(
        rows_for(families, 20), families, samples=20, resamples=100
    )
    assert result["family_count"] == 2
    assert result["task_count"] == 3
    assert result["cost_saving_fraction"] == pytest.approx(0.2)
    assert result["quality_delta_95_interval"] == [0, 0]
    assert not result["accepted"]
    assert "fewer_than_eight_task_families" in result["reasons"]


@pytest.mark.parametrize("fault", ["missing", "duplicate", "nan", "unfinished"])
def test_incomplete_or_invalid_provider_evidence_cannot_pass(fault):
    families = {"a": "one", "b": "two"}
    rows = rows_for(families)
    if fault == "missing":
        rows.pop()
    elif fault == "duplicate":
        rows.append(deepcopy(rows[-1]))
    elif fault == "nan":
        rows[-1]["session"]["cost_usd"] = float("nan")
    else:
        rows[-1].pop("passed")
    result = experiments.assess_comparison(rows, families, samples=2)
    assert result["status"] == "invalid" and not result["accepted"]


def test_opposing_family_effects_show_uncertainty():
    families = {"a": "one", "b": "two"}
    rows = rows_for(families)
    for row in rows:
        if row["view"] == "candidate":
            row["session"]["cost_usd"] = 0.5 if row["case"] == "a" else 1.5
    report = experiments.assess_comparison(rows, families, samples=2)
    low, high = report["cost_saving_95_interval"]
    assert low < 0 < high
    assert "five_percent_cost_saving_not_established" in report["reasons"]


def test_pending_review_is_not_a_false_answer_or_a_quality_verdict():
    families = {"a": "one", "b": "two"}
    rows = rows_for(families)
    for row in rows:
        row.update(outcome="review", claim_review_required=True, passed=False)
    report = experiments.assess_comparison(rows, families, samples=2)
    assert report["quality_delta"] is None
    assert report["quality_delta_95_interval"] is None
    assert report["candidate_hard_failures"] == 0
    assert report["sessions_requiring_claim_review"] == len(rows)
    assert not report["accepted"]


@pytest.mark.anyio
async def test_operator_stop_prevents_opening_provider(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from simba_mcp.evaluation.hosts import __main__ as command

    stop = tmp_path / "stop"
    stop.touch()
    monkeypatch.setattr(command, "client", lambda _: pytest.fail("Provider must not open"))
    with pytest.raises(RuntimeError, match="Operator requested stop"):
        await command.run(
            SimpleNamespace(
                output=tmp_path / "evidence.json",
                cap_usd=25,
                prior_usd=11.438494,
                samples=2,
                mode="eager",
                case=None,
                stop_file=stop,
            )
        )


@pytest.mark.anyio
async def test_development_tasks_are_achievable_with_canonical_dispatch():
    for task in development_tasks():
        dispatch = ResultSelectionDispatch(create_server(), task)
        _, error = await dispatch(
            "get_model_results",
            {
                "model_hash": "result-example",
                "sections": ",".join(sorted(task.required_sections)),
            },
        )
        assert not error, task.id
        assert all(dispatch.grade(task.expected).values()), task.id


@pytest.mark.parametrize(
    "text, expected",
    [
        ('{"roi": 2.5}', True),
        ('```json\n{"roi": 2.5}\n```', True),
        ('This proves causality. ```json\n{"roi": 2.5}\n```', False),
        ('```json\n{"roi": 2.5}\n``` Invest everything.', False),
    ],
)
def test_formatting_is_separate_from_unreviewed_prose(text, expected):
    assert structured_answer_only(text) is expected
