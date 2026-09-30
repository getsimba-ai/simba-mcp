"""Compact wording must not change contracts or execution behaviour."""

import anyio
import pytest

from simba_mcp.catalogue import COMPACT
from simba_mcp.evaluation.cases import cases
from simba_mcp.evaluation.runner import run_case
from simba_mcp.server import create_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_only_curated_descriptions_change():
    legacy = anyio.run(create_server("legacy").list_tools)
    compact = anyio.run(create_server("compact").list_tools)
    changed = set()
    for before, after in zip(legacy, compact, strict=True):
        a, b = before.model_dump(), after.model_dump()
        if a.pop("description") != b.pop("description"):
            changed.add(before.name)
        assert a == b
    assert changed == set(COMPACT)


@pytest.mark.anyio
@pytest.mark.parametrize("case", cases(), ids=lambda case: case.id)
async def test_compact_dispatch_preserves_synthetic_workflows(case):
    result = await run_case(case, mcp_server=create_server("compact"))
    assert result.passed, result.assertions
    assert result.unintended_writes == 0


def test_invalid_mode_is_not_silently_accepted():
    with pytest.raises(ValueError):
        create_server("typo")

@pytest.mark.parametrize("mode", ["legacy", "compact"])
def test_results_identity_requires_channel_map_not_spelling(mode):
    tools = {tool.name: tool for tool in anyio.run(create_server(mode).list_tools)}
    description = tools["get_model_results"].description
    assert "retrieve channel_map" in description
    assert "do not infer identity from spelling" in description
    assert "Start with channel_summary or channel_map" not in description


@pytest.mark.parametrize("mode", ["legacy", "compact"])
def test_every_registration_uses_the_original_wire_wrapper(monkeypatch, mode):
    from simba_mcp import server

    registered = []
    original = server.SimbaMCPServer.add_tool

    def record(instance, handler, **kwargs):
        registered.append(handler.__wrapped__)
        return original(instance, handler, **kwargs)

    monkeypatch.setattr(server.SimbaMCPServer, "add_tool", record)
    create_server(mode)
    assert registered == list(server.TOOLS)


@pytest.mark.anyio
async def test_observer_receives_actual_results_without_polluting_report():
    import json

    observed = []
    trial = await run_case(cases()[0], observe_result=observed.append)
    assert trial.passed
    assert observed[0]["status"] == "complete"
    assert observed[1]["channel_summary"][0]["ROI"] == 2.0
    assert "model-example" not in json.dumps(trial.model_dump())


def test_legacy_is_default_and_full_contracts_are_preserved():
    import inspect

    from simba_mcp import guidance, reference
    from simba_mcp.server import TOOLS

    tools = {tool.name: tool for tool in anyio.run(create_server().list_tools)}
    for handler in TOOLS:
        assert inspect.cleandoc(tools[handler.__name__].description) == inspect.getdoc(handler)
        if handler.__name__ in COMPACT:
            entry = COMPACT[handler.__name__]
            response = guidance.read_guidance(entry.topic, "tool-reference")
            assert inspect.getdoc(handler) in response["content"]
            assert len(entry.text) < len(inspect.getdoc(handler))
    assert reference.DOCS.with_name("tools-compact.md").read_text(
        encoding="utf-8"
    ) == reference.current("compact")
