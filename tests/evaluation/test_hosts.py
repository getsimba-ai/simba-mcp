import json
from types import SimpleNamespace

import httpx
import pytest

from simba_mcp.evaluation.hosts.anthropic import Budget, definitions, session
from simba_mcp.evaluation.hosts.scenarios import answer


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_definitions_preserve_schemas_and_eager_fallback():
    tool = SimpleNamespace(name="read", description="Read", input_schema={"type": "object"})
    original = dict(tool.input_schema)
    eager = definitions([tool], "eager")
    deferred = definitions([tool], "deferred")
    assert deferred[1].pop("defer_loading") is True
    assert deferred[1] == eager[0]
    deferred[1]["input_schema"]["new"] = True
    assert tool.input_schema == original
    with pytest.raises(ValueError):
        definitions([tool], "missing")


@pytest.mark.anyio
async def test_search_history_zero_results_pause_and_dispatch():
    search = {
        "type": "tool_search_tool_result",
        "tool_use_id": "search",
        "content": {"type": "tool_search_tool_search_result", "tool_references": []},
    }
    found = {
        **search,
        "content": {
            "type": "tool_search_tool_search_result",
            "tool_references": [{"type": "tool_reference", "tool_name": "read"}],
        },
    }
    requests = []
    responses = [
        ([search], "pause_turn"),
        ([found, {"type": "tool_use", "id": "call", "name": "read", "input": {}}], "tool_use"),
        ([{"type": "text", "text": "{}"}], "end_turn"),
    ]

    def transport(request):
        requests.append(json.loads(request.content))
        blocks, stop = responses.pop(0)
        return httpx.Response(
            200,
            json={
                "content": blocks,
                "stop_reason": stop,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    calls = []

    async def dispatch(name, arguments):
        calls.append(name)
        return {"ok": True}, False

    snapshots = []
    budget = Budget(1)
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        record = await session(
            client, [], "read", dispatch, budget, lambda _: snapshots.append(budget.reserved)
        )
    assert calls == ["read"]
    assert requests[1]["messages"][1]["content"] == [search]
    assert requests[2]["messages"][2]["content"][0] == found
    assert requests[2]["messages"][-1]["content"][0]["tool_use_id"] == "call"
    assert snapshots[0] > 0
    assert budget.reserved == 0
    assert record["stop"] == "end_turn"


@pytest.mark.anyio
async def test_provider_failure_never_replays_mutation_or_switches_mode():
    requests = []

    def transport(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                    "stop_reason": "tool_use",
                    "content": [{"type": "tool_use", "id": "write", "name": "create", "input": {}}],
                },
            )
        return httpx.Response(400)

    writes = []

    async def dispatch(name, arguments):
        writes.append(name)
        return {"queued": True}, False

    budget = Budget(1)
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(RuntimeError, match="no replay"):
            await session(client, [], "create once", dispatch, budget, lambda _: None)
    assert writes == ["create"]
    assert len(requests) == 2
    assert budget.reserved > 0


def test_budget_carries_prior_and_unknown_usage():
    budget = Budget(10, prior=9.99)
    with pytest.raises(RuntimeError, match="exhausted"):
        budget.reserve({"max_tokens": 1200})
    budget = Budget(10, prior=5)
    reserved = budget.reserve({"max_tokens": 1200})
    with pytest.raises(ValueError):
        budget.settle({}, reserved)
    assert budget.reserved == reserved


def test_format_failure_is_separate_from_correct_facts():
    assert answer('Here it is: ```json\n{"status":"pending"}\n```') == (
        {"status": "pending"},
        False,
    )
    assert answer('{"status":"pending"}') == ({"status": "pending"}, True)


@pytest.mark.anyio
async def test_new_session_discards_previous_search_context():
    requests = []

    def transport(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "{}"}],
            },
        )

    async def dispatch(*_):
        raise AssertionError("No execution authorised")

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as provider:
        for prompt in ("first task", "new task after context reset"):
            await session(provider, [], prompt, dispatch, Budget(1), lambda _: None)
    assert requests[1]["messages"] == [{"role": "user", "content": "new task after context reset"}]


@pytest.mark.anyio
async def test_cross_domain_sequence_reuses_canonical_dispatch():
    from simba_mcp.evaluation.contracts import Case
    from simba_mcp.evaluation.hosts.scenarios import SyntheticDispatch, tasks
    from simba_mcp.server import create_server

    analysis, _, _ = tasks()[0]
    study, _, _ = tasks()[2]
    combined = Case(
        id="cross_domain", purpose="Results then study evidence", steps=analysis.steps + study.steps
    )
    dispatch = SyntheticDispatch(create_server("compact"), combined)
    for step in combined.steps:
        _, error = await dispatch(step.tool, step.arguments)
        assert not error
    assert dispatch.completed == 3
    assert dispatch.unintended_writes == 0


@pytest.mark.anyio
async def test_cli_zero_budget_stops_before_network_and_keeps_ledger(tmp_path, monkeypatch):
    from simba_mcp.evaluation.hosts.__main__ import run

    async def forbidden(*args, **kwargs):
        raise AssertionError("Zero budget must not send a provider request")

    monkeypatch.setattr(httpx.AsyncClient, "post", forbidden)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-test-key")
    output = tmp_path / "evidence.json"
    args = SimpleNamespace(
        output=output, cap_usd=0, prior_usd=0, case="analyse_model", mode="eager", samples=1
    )
    with pytest.raises(RuntimeError, match="exhausted"):
        await run(args)
    report = json.loads(output.read_text())
    assert report["status"] == "stopped"
    assert report["budget"]["charged"] == 0
    assert "synthetic-test-key" not in output.read_text()
    with pytest.raises(ValueError, match="overwrite"):
        await run(args)
