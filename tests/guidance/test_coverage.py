"""Negative drift fixtures protect explicit decisions, schemas, counts and links."""

from copy import deepcopy

import anyio
import pytest
from jsonschema.exceptions import ValidationError

from simba_mcp import guidance
from simba_mcp.evaluation.role_workflows import role_workflows
from simba_mcp.guidance.coverage import (
    DECISIONS,
    generated_outputs,
    render_counts,
    replace_counts,
    validate_coverage,
    validate_links,
)
from simba_mcp.profiles import PROFILES
from simba_mcp.server import create_server


def tools():
    return anyio.run(create_server().list_tools)


def test_current_decisions_examples_and_generated_outputs_are_current():
    registered = tools()
    workflows = role_workflows()
    validate_coverage(registered, PROFILES, DECISIONS, workflows)
    for path, content in generated_outputs(registered, PROFILES, DECISIONS, workflows).items():
        assert path.read_text(encoding="utf-8") == content, path


def test_unclassified_new_tool_fails_until_explicit_exclusion():
    registered = tools()
    new = registered[0].model_copy(update={"name": "synthetic_new_admin_operation"})
    with pytest.raises(AssertionError, match="Unclassified registered tools"):
        validate_coverage([*registered, new], PROFILES, DECISIONS, role_workflows())
    decisions = deepcopy(DECISIONS)
    decisions.append(
        {
            "family": "synthetic_admin",
            "tools": [new.name],
            "roles": [],
            "reason": "Full-only administration is outside evidence roles.",
            "guidance": ["mmm"],
            "examples": [],
            "example_limitation": "No new narrow-role job; full fallback is explicit.",
        }
    )
    validate_coverage([*registered, new], PROFILES, decisions, role_workflows())


def test_removed_required_tool_fails_with_named_dependency():
    with pytest.raises(AssertionError, match="removed tool: get_upload"):
        validate_coverage(
            [tool for tool in tools() if tool.name != "get_upload"],
            PROFILES,
            DECISIONS,
            role_workflows(),
        )


def test_missing_guidance_decision_fails_and_explicit_limitation_is_accepted():
    decisions = deepcopy(DECISIONS)
    decisions[0]["guidance"] = []
    with pytest.raises(AssertionError, match="Missing guidance decision"):
        validate_coverage(tools(), PROFILES, decisions, role_workflows())
    decisions[0]["guidance_limitation"] = (
        "Intentional test-only exclusion: no standalone guidance; exact tool contract remains available."
    )
    validate_coverage(tools(), PROFILES, decisions, role_workflows())


def test_required_profile_dependency_cannot_be_removed_silently():
    profiles = {**PROFILES, "marketer": PROFILES["marketer"] - {"get_data_report"}}
    with pytest.raises(AssertionError, match="marketer membership: get_data_report"):
        validate_coverage(tools(), profiles, DECISIONS, role_workflows())


def test_invalid_example_payload_fails_schema_validation():
    workflows = deepcopy(role_workflows())
    workflows[0].case.steps[0].arguments["limit"] = ["invalid"]
    with pytest.raises(ValidationError):
        validate_coverage(tools(), PROFILES, DECISIONS, workflows)


def test_example_cannot_claim_an_excluded_profile():
    from dataclasses import replace

    workflows = role_workflows()
    index = next(i for i, item in enumerate(workflows) if item.case.id == "create_mmm")
    workflows[index] = replace(workflows[index], roles=("marketer",))
    with pytest.raises(AssertionError, match="create_model excluded from marketer"):
        validate_coverage(tools(), PROFILES, DECISIONS, workflows)


def test_stale_current_counts_are_detected_without_touching_history():
    registered = tools()
    correct = render_counts(registered, PROFILES)
    stale = correct.replace(f"| `marketer` | {len(PROFILES['marketer'])} |", "| `marketer` | 1 |")
    assert replace_counts(stale, registered, PROFILES) != stale
    assert replace_counts(correct, registered, PROFILES) == correct
    history = "Historical trial: 81/37/38 tools.\n" + stale
    assert replace_counts(history, registered, PROFILES).startswith(
        "Historical trial: 81/37/38 tools."
    )


def test_all_native_links_resolve_and_broken_links_fail(tmp_path):
    from simba_mcp.guidance.__main__ import export

    export(tmp_path)
    for entry in guidance.MANIFEST["topics"].values():
        folder = tmp_path / entry["skill"]
        paths = {path.relative_to(folder).as_posix() for path in folder.rglob("*.md")}
        for relative in paths:
            validate_links((folder / relative).read_text(encoding="utf-8"), paths, relative)
    with pytest.raises(AssertionError, match="Broken guidance link"):
        validate_links("[missing](references/missing.md)", {"SKILL.md"})


def test_every_current_example_is_reachable_from_its_native_entrypoint():
    for item in role_workflows():
        entry = guidance.MANIFEST["topics"][item.topic]
        section = item.section + "-examples"
        path = entry["sections"][section]
        assert item.case.id in guidance.CONTENT.joinpath(path).read_text(encoding="utf-8")
        assert section + ".md" in guidance.CONTENT.joinpath(
            entry["sections"]["entrypoint"]
        ).read_text(encoding="utf-8")


def test_current_host_assignments_keep_historical_paid_cases_separate():
    from simba_mcp.evaluation.hosts.roles import ROLE_CASES, current_role_cases
    from simba_mcp.evaluation.hosts.scenarios import current_role_tasks

    assert "role_actual_data" not in ROLE_CASES["marketer"]
    assert "role_actual_data" in current_role_cases()["marketer"]
    assert {case.id for case, _, _ in current_role_tasks()} == {
        item.case.id for item in role_workflows()
    }
