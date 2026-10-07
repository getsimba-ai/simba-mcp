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


def test_v21_named_deltas_accept_grouping_without_hiding_conflicts():
    from simba_mcp.evaluation.hosts.result_selection import ResultTask

    task = ResultTask(
        "role_saved_allocation",
        "Compare saved runs as JSON",
        frozenset(),
        {"runs": [1, 2], "spend_delta": 10, "revenue_delta": 20, "roi_delta": 0.5},
    )
    facts = {"runs": [1, 2], "deltas": {k: v for k, v in task.expected.items() if k != "runs"}}
    assert not semantic_facts(task, facts, set(), grader_version=20)
    assert semantic_facts(task, facts, set(), grader_version=21)
    assert claims_in_scope(task, facts, grader_version=21)
    for bad in (
        {**facts, "spend_delta": 99},
        {**facts, "deltas": {**facts["deltas"], "spend_delta": True}},
    ):
        assert not semantic_facts(task, bad, set(), grader_version=21)
    extra = {**facts, "deltas": {**facts["deltas"], "causal_effect": 20}}
    assert semantic_facts(task, extra, set(), grader_version=21)
    assert not claims_in_scope(task, extra, grader_version=21)
    assert not claims_in_scope(task, {**facts, "explanation": "causal proof"}, grader_version=21)


def test_v21_supported_facts_do_not_silently_accept_added_claims():
    from simba_mcp.evaluation.hosts.result_grading import fact_verdict
    from simba_mcp.evaluation.hosts.result_selection import ResultTask

    task = ResultTask(
        "study_review",
        "Return status and reason as JSON",
        frozenset(),
        {"status": "unknown", "reason": "not_returned"},
    )
    facts = {**task.expected, "metric": "revenue"}
    assert fact_verdict(task, facts, set(), grader_version=21) == "pass"
    assert not claims_in_scope(task, facts, grader_version=21)
    assert not semantic_facts(task, {**facts, "status": "passed"}, set(), grader_version=21)


def test_v21_requires_explicit_nullable_fields():
    from simba_mcp.evaluation.hosts.result_grading import fact_verdict
    from simba_mcp.evaluation.hosts.result_selection import ResultTask

    for field in ("predicted_outcome", "preferred_run_id", "curve_point"):
        task = ResultTask("required_nullable", "Return saved fields", frozenset(), {field: None})
        assert semantic_facts(task, {field: None}, set(), grader_version=21)
        assert fact_verdict(task, {}, set(), grader_version=21) == "fail"


def test_v21_merges_compatible_metadata_but_requires_claim_review():
    from simba_mcp.evaluation.hosts.result_selection import ResultTask

    task = ResultTask(
        "role_campaign_budget",
        "Return campaign allocation",
        frozenset(),
        {"channel": "search", "provenance": {"curve_revision": "r", "map_version": 3}},
    )
    facts = {
        "provenance": {**task.expected["provenance"], "context_key": "c"},
        "allocation": [{"channel": "search", "provenance": task.expected["provenance"]}],
    }
    assert semantic_facts(task, facts, set(), grader_version=21)
    assert not claims_in_scope(task, facts, grader_version=21)
    conflict = {**facts, "allocation": [{"channel": "search", "provenance": {"map_version": True}}]}
    assert not semantic_facts(task, conflict, set(), grader_version=21)


def test_v21_unknown_refusal_explanations_require_review():
    from simba_mcp.evaluation.hosts.result_grading import fact_verdict
    from simba_mcp.evaluation.hosts.result_selection import ResultTask

    task = ResultTask(
        "role_experiment_unsupported",
        "Hand off unsupported operation",
        frozenset(),
        {"available": False, "reason": "unsupported_operation", "next_action": "handoff"},
    )
    facts = {**task.expected, "reason": "Novel explanation requiring evidence review"}
    assert fact_verdict(task, facts, set(), grader_version=21) == "review"
    extended_handoff = {
        **facts,
        "next_action": "handoff: Check whether this backend supports the requested operation.",
    }
    assert fact_verdict(task, extended_handoff, set(), grader_version=21) == "review"
    assert fact_verdict(task, {**facts, "available": True}, set(), grader_version=21) == "fail"
