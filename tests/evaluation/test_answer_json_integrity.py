"""Independent task-audit reproductions that could reverse a quality conclusion."""

import pytest

from simba_mcp.evaluation.hosts.result_grading import (
    claims_in_scope,
    semantic_facts,
    structured_answer_only,
)
from simba_mcp.evaluation.hosts.result_selection import ResultTask
from simba_mcp.evaluation.hosts.scenarios import answer
from simba_mcp.evaluation.json_data import load_json


@pytest.mark.parametrize(
    "raw",
    [
        '{"roi":999,"roi":2.5}',
        '{"result":{"roi":999,"roi":2.5}}',
        '{"roi":NaN}',
        '{"roi":Infinity}',
        '{"roi":-Infinity}',
        '{"roi":1e999}',
    ],
)
def test_contradictory_or_nonfinite_answers_cannot_be_accepted(raw):
    with pytest.raises(ValueError):
        load_json(raw)
    assert answer(raw) == (None, False)
    assert answer("```json\n" + raw + "\n```") == (None, False)
    assert not structured_answer_only(raw)
    assert not structured_answer_only("```json\n" + raw + "\n```")


def test_valid_finite_answers_retain_format_and_claim_review_distinctions():
    raw = '{"roi":2.5,"evidence":{"spend":200}}'
    expected = {"roi": 2.5, "evidence": {"spend": 200}}
    assert answer(raw) == (expected, True)
    assert answer("```json\n" + raw + "\n```") == (expected, False)
    assert structured_answer_only("```json\n" + raw + "\n```")
    assert answer("Unsupported causal claim.\n```json\n" + raw + "\n```") == (expected, False)
    assert not structured_answer_only("Unsupported causal claim.\n```json\n" + raw + "\n```")


def test_prospective_absence_equivalence_uses_exact_contract_not_broad_family():
    expected = {"available": False, "reason": "fitted_before_mroi_periods"}
    task = ResultTask(
        "result_old_artifact", "Read saved absence", frozenset(), expected, family="results"
    )
    nested = {"mroi_periods": expected}
    assert not semantic_facts(task, nested, set(), grader_version=17)
    assert not claims_in_scope(task, nested, grader_version=17)
    assert semantic_facts(task, nested, set(), grader_version=20)
    assert claims_in_scope(task, nested, grader_version=20)
    contradictory = {"available": True, "mroi_periods": expected}
    assert not semantic_facts(task, contradictory, set(), grader_version=20)
    assert not claims_in_scope(task, contradictory, grader_version=20)
    invalid_boolean = {"available": 0, "mroi_periods": expected}
    assert not semantic_facts(task, invalid_boolean, set(), grader_version=20)
    assert not claims_in_scope(task, invalid_boolean, grader_version=20)
    extra_claim = {"mroi_periods": {**expected, "explanation": "This proves convergence"}}
    assert not claims_in_scope(task, extra_claim, grader_version=20)
    different = ResultTask(
        "different_absence", "Different reason", frozenset(), expected, family="results"
    )
    assert not semantic_facts(different, nested, set(), grader_version=20)
