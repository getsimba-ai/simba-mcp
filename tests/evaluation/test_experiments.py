"""Protect experimental validity rather than rewarding a particular candidate."""

from copy import deepcopy

import pytest

from simba_mcp.evaluation import experiments
from simba_mcp.evaluation.hosts.result_calibration import calibrate
from simba_mcp.evaluation.hosts.result_grading import structured_answer_only
from simba_mcp.evaluation.hosts.result_selection import (
    ResultSelectionDispatch,
    development_tasks,
    validation_tasks,
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

    monkeypatch.setattr(result_calibration, "semantic_facts", lambda *_, **__: True)
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
    assert "required_cost_saving_not_established" in report["reasons"]


def test_agreed_thresholds_do_not_grant_independent_acceptance():
    families = {"a": "one", "b": "two"}
    rows = rows_for(families)
    for row in rows:
        row["noncontributing_result_calls"] = 0
    limits = {
        "minimum_supported_answer_rate": 0.95,
        "minimum_cost_saving": 0.0,
        "quality_noninferiority_margin": 0.0,
    }
    report = experiments.assess_comparison(rows, families, samples=2, thresholds=limits)
    assert "thresholds_require_owner_agreement" not in report["reasons"]
    assert report["candidate_supported_answer_rate"] == 1.0
    assert not report["accepted"]
    rows[0]["noncontributing_result_calls"] = 2 if rows[0]["view"] == "candidate" else 0
    for row in rows:
        if row["view"] == "candidate":
            row["noncontributing_result_calls"] = 1
    report = experiments.assess_comparison(rows, families, samples=2, thresholds=limits)
    assert "noncontributing_calls_not_nonincreasing" in report["reasons"]


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


@pytest.mark.anyio
@pytest.mark.parametrize("name", ("result_roi", "result_tv_roi", "result_total_roi"))
async def test_dated_summary_counts_when_the_task_declares_no_window(name):
    task = next(t for t in development_tasks() if t.id == name)
    dispatch = ResultSelectionDispatch(create_server(), task)
    _, error = await dispatch(
        "get_model_results",
        {
            "model_hash": "result-example",
            "sections": ",".join(sorted(task.required_sections)),
            "start": "2025-01-01",
            "end": "2025-02-28",
        },
    )
    assert not error, name
    assert dispatch.grade(task.expected)["required_evidence"], name


@pytest.mark.anyio
async def test_a_window_with_different_totals_is_not_credited():
    task = next(t for t in development_tasks() if t.id == "result_roi")
    dispatch = ResultSelectionDispatch(create_server(), task)
    _, error = await dispatch(
        "get_model_results",
        {
            "model_hash": "result-example",
            "sections": "channel_summary,channel_map",
            "start": "2025-01-01",
            "end": "2025-01-01",
        },
    )
    assert not error
    assert not dispatch.grade(task.expected)["required_evidence"]


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


@pytest.mark.anyio
@pytest.mark.parametrize("sections", ["coefficients", "channel_summary"])
async def test_period_aggregation_accepts_either_sufficient_evidence_source(sections):
    task = next(t for t in development_tasks() if t.id == "result_period_roi")
    dispatch = ResultSelectionDispatch(create_server(), task)
    await dispatch("get_model_results", {"model_hash": "result-example", "sections": sections})
    assert all(dispatch.grade(task.expected).values())


@pytest.mark.anyio
async def test_generated_validation_has_new_truth_and_preserves_evidence_constraints():
    suite = validation_tasks(123456, 2)
    assert {t.id.rsplit("_dataset_", 1)[0] for t in suite} == {t.id for t in development_tasks()}
    assert len({t.id for t in suite}) == len(suite)
    assert len({t.dataset for t in suite}) == 2
    search = [t for t in suite if t.id.startswith("result_roi_")]
    assert search[0].expected != search[1].expected
    for task in suite:
        dispatch = ResultSelectionDispatch(create_server(), task)
        assert not dispatch.grade(task.expected)["required_evidence"]
        _, error = await dispatch(
            "get_model_results",
            {
                "model_hash": "result-example",
                "sections": ",".join(sorted(task.required_sections)),
            },
        )
        assert not error and all(dispatch.grade(task.expected).values()), task.id


@pytest.mark.anyio
async def test_generated_validation_cli_freezes_fixture_and_excludes_oracle_from_prompt(
    tmp_path, monkeypatch
):
    import json
    from types import SimpleNamespace

    import httpx

    from simba_mcp.evaluation.hosts import __main__ as command
    from simba_mcp.guidance import read_guidance

    seen = []

    async def fake_session(provider, tools, prompt, dispatch, budget, checkpoint, **kwargs):
        seen.append(prompt)
        assert str(dispatch.task.expected) not in prompt
        await dispatch(
            "get_model_results",
            {
                "model_hash": "result-example",
                "sections": ",".join(sorted(dispatch.task.required_sections)),
            },
        )
        result = {
            "final_text": json.dumps(dispatch.task.expected),
            "cost_usd": 0.0,
            "calls": [],
            "responses": [],
            "seconds": 0.0,
        }
        checkpoint(result)
        return result

    monkeypatch.setattr(command, "session", fake_session)
    monkeypatch.setattr(command, "client", lambda _: httpx.AsyncClient())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-key")
    # Source hashing is exercised separately; avoid repeated filesystem reads in this integration test.
    monkeypatch.setattr(experiments, "source_fingerprint", lambda: "frozen-source")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                s: read_guidance("results", s)
                for s in ("entrypoint", "interpretation", "tool-reference")
            }
        )
    )
    output = tmp_path / "report.json"
    await command.run(
        SimpleNamespace(
            output=output,
            cap_usd=25,
            prior_usd=11.438494,
            samples=2,
            mode="eager",
            case=None,
            results_baseline=baseline,
            results_robust=True,
            results_validation_datasets=2,
        )
    )
    report = json.loads(output.read_text())
    assert report["status"] == "complete" and len(seen) == len(report["trials"])
    assert all(t["passed"] for t in report["trials"])
    assert report["configuration"]["validation_seed"] is not None
    assert all(t["case"]["fixture"] for t in report["tasks"])
    assert report["assessment"]["dataset_count"] == 2
    assert not report["assessment"]["accepted"]


def test_reviewed_assessment_requires_complete_hash_bound_reviews():
    from hashlib import sha256

    rows = rows_for({"a": "one", "b": "two"})
    for row in rows:
        row["session"]["final_text"] = "{}"
        row["trajectory"] = []
        row["read_authorisation"] = {"unauthorised_reads": 0, "unauthorised_read_attempts": 0}
    report = {
        "trials": rows,
        "tasks": [
            {"case": {"id": case, "family": family, "dataset": "synthetic"}}
            for case, family in {"a": "one", "b": "two"}.items()
        ],
        "configuration": {"samples": 2},
        "experiment_inputs": {
            "purpose": "candidate_acceptance",
            "case_review": {"verified": True},
            "acceptance_thresholds": {
                "minimum_supported_answer_rate": 0.95,
                "minimum_cost_saving": 0,
                "quality_noninferiority_margin": 0,
            },
        },
    }
    reviews = [
        {
            **{k: r[k] for k in ("case", "view", "repetition")},
            "answer_sha256": sha256(b"{}").hexdigest(),
            "trajectory_sha256": experiments.fingerprint([]),
            "claims": "supported",
            "supported_answer": True,
            "rationale": "Synthetic labelled test",
            "calls": [],
        }
        for r in rows
    ]
    assert experiments.assess_reviewed_comparison(report, reviews)["accepted"]
    assert all(r["passed"] for r in rows)
    with pytest.raises(ValueError, match="coverage"):
        experiments.assess_reviewed_comparison(report, reviews[:-1])
    bad = deepcopy(reviews)
    bad[0]["answer_sha256"] = "changed"
    with pytest.raises(ValueError, match="answer changed"):
        experiments.assess_reviewed_comparison(report, bad)
    bad = deepcopy(reviews)
    next(r for r in bad if r["view"] == "candidate")["claims"] = "unsupported"
    assert not experiments.assess_reviewed_comparison(report, bad)["accepted"]
    bad = deepcopy(reviews)
    bad[0]["claims"] = "inconclusive"
    assert not experiments.assess_reviewed_comparison(report, bad)["accepted"]
    for key in ("executed", "required_evidence", "no_unintended_writes"):
        unsafe = deepcopy(report)
        next(r for r in unsafe["trials"] if r["view"] == "candidate")["assertions"][key] = False
        assert not experiments.assess_reviewed_comparison(unsafe, reviews)["accepted"]
