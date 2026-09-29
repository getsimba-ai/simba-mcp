"""Native Skills and fallback use the same bounded, independently installable content."""

import hashlib
import json
import re
import socket
from pathlib import Path

import pytest

from simba_mcp import guidance
from simba_mcp.guidance.__main__ import export
from simba_mcp.server import mcp


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_export_is_current_and_each_skill_is_self_contained(tmp_path):
    assert export(Path(__file__).parents[2] / "skills", check=True)
    export(tmp_path)
    for topic, entry in guidance.MANIFEST["topics"].items():
        folder = tmp_path / entry["skill"]
        entrypoint = (folder / "SKILL.md").read_text(encoding="utf-8")
        assert f"name: {folder.name}\n" in entrypoint
        assert len(entrypoint.splitlines()) < 100
        for relative in re.findall(r"\]\((references/[^)]+)\)", entrypoint):
            assert (folder / relative).is_file()
            section = Path(relative).stem
            response = guidance.read_guidance(topic, section)
            content = (folder / relative).read_text(encoding="utf-8")
            assert response["content"] == content
            assert response["content_sha256"] == hashlib.sha256(content.encode()).hexdigest()
        assert "../" not in entrypoint


@pytest.mark.parametrize(
    "topic,section",
    [
        ("../../README", "entrypoint"),
        ("results", "../../README"),
        ("index", "unknown"),
        ("unknown", "entrypoint"),
        ("results", "C:/secret"),
    ],
)
def test_unknown_identifiers_refuse_without_path_reads(topic, section, monkeypatch):
    class Forbidden:
        def joinpath(self, *args):
            pytest.fail("Untrusted identifiers must not reach resource lookup")

    monkeypatch.setattr(guidance, "CONTENT", Forbidden())
    response = guidance.read_guidance(topic, section)
    assert response["_status_code"] == 400
    assert response["_error_code"] == "unknown_guidance"
    assert "content" not in response


def test_every_section_and_index_fit_the_wire_budget():
    index = guidance.read_guidance()
    assert index["guidance_version"] == "1"
    for row in index["topics"]:
        for section in row["sections"]:
            result = guidance.read_guidance(row["topic"], section)
            assert "content" in result
            assert (
                len(json.dumps(result, ensure_ascii=False).encode()) <= guidance.MAX_RESPONSE_BYTES
            )


def test_oversized_content_is_refused_not_truncated(monkeypatch):
    monkeypatch.setattr(guidance, "MAX_RESPONSE_BYTES", 10)
    result = guidance.read_guidance("results")
    assert result["_status_code"] == 413
    assert "content" not in result


@pytest.mark.anyio
async def test_real_dispatch_needs_no_socket_and_preserves_error_envelope(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Guidance must not contact a backend")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    good = await mcp.call_tool("get_workflow_guidance", {"topic": "results"})
    assert not good.is_error
    assert good.structured_content["guidance_version"] == "1"
    bad = await mcp.call_tool("get_workflow_guidance", {"topic": "../secret"})
    assert bad.is_error
    assert bad.structured_content["_error_code"] == "unknown_guidance"


def test_shared_prior_reference_has_one_canonical_owner():
    topics = guidance.MANIFEST["topics"]
    assert topics["mmm"]["sections"]["priors"] == topics["priors"]["sections"]["conventions"]


def test_referenced_tools_resolve_in_current_catalogue():
    from simba_mcp.server import TOOLS

    known = {tool.__name__ for tool in TOOLS}
    pattern = (
        r"`((?:get|list|run|create|update|publish|launch|cancel|upload|save|rename|delete|"
        r"adopt|refreeze|revise|validate|diff|evaluate|set|import|link|unlink)_[a-z_]+)(?:`|\()"
    )
    for entry in guidance.MANIFEST["topics"].values():
        for path in entry["sections"].values():
            content = guidance.CONTENT.joinpath(path).read_text(encoding="utf-8")
            assert set(re.findall(pattern, content)) - {"run_id"} <= known, path


def test_existing_results_need_no_startup_discovery():
    from simba_mcp.evaluation.cases import cases

    case = next(c for c in cases() if c.id == "analyse_model")
    assert not {"get_backend_capabilities", "get_data_schema"} & {s.tool for s in case.steps}


def test_documented_control_prior_example_matches_tool_schema():
    from pydantic import TypeAdapter

    from simba_mcp.schemas import ControlPrior

    content = guidance.read_guidance("priors", "conventions")["content"]
    example = json.loads(re.search(r"```json\n(.*?)\n```", content, re.DOTALL).group(1))
    for prior in example["control_priors"]:
        TypeAdapter(ControlPrior).validate_python(prior)
