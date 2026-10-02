"""Prospective semantics must not weaken historical task contracts."""

from simba_mcp.evaluation.hosts.result_calibration import GRADER_VERSION, calibrate
from simba_mcp.evaluation.hosts.result_grading import claims_in_scope, semantic_facts
from simba_mcp.evaluation.hosts.result_rlc_tasks import rlc_tasks
from simba_mcp.evaluation.result_acceptance_v4 import acceptance_v4_tasks


def test_all_calibration_labels_and_critical_cases_match():
    report = calibrate()
    assert GRADER_VERSION == 17
    assert len(report["cases"]) >= 30
    assert len({row["id"] for row in report["cases"]}) == len(report["cases"])
    assert report["passed"], [r["id"] for r in report["cases"] if not r["passed"]]


def test_historical_task_does_not_gain_prospective_schema_equivalences():
    old = next(t for t in acceptance_v4_tasks() if t.id == "v4_attribution_absence")
    prospective = rlc_tasks()[0]
    assert "Explicitly explain" not in old.prompt
    assert "Explicitly explain" in prospective.prompt
    assert old.expected == prospective.expected
    nested = {"answer": old.expected}
    assert not semantic_facts(old, nested, set())
    assert semantic_facts(prospective, nested, set())


def test_reversed_duplicate_order_cannot_hide_contradiction():
    task = rlc_tasks()[0]
    for facts in (
        {"additive": True, **task.expected},
        {**task.expected, "additive": True},
        {"first_week": {"modelled_visits": 56}, **task.expected},
    ):
        assert not semantic_facts(task, facts, set())
        assert not claims_in_scope(task, facts)


def test_unfamiliar_container_is_not_silently_flattened():
    task = rlc_tasks()[0]
    facts = {**task.expected, "unsupported_explanation": {"is_additive": True}}
    assert semantic_facts(task, facts, set())
    assert not claims_in_scope(task, facts)
