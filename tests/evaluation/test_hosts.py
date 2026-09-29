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


def test_sonnet_pricing_and_model_bound_reservation():
    from simba_mcp.evaluation.hosts.anthropic import MODEL, SONNET, model_configuration

    request = model_configuration(SONNET)["request"]
    assert "temperature" not in request
    budget = Budget(3, model=SONNET)
    reserved = budget.reserve(request)
    cost = budget.settle(
        {
            "input_tokens": 1000,
            "output_tokens": 2000,
            "cache_read_input_tokens": 100,
            "cache_creation_input_tokens": 100,
        },
        reserved,
    )
    assert cost == pytest.approx(0.02242)
    assert budget.reserved == 0
    with pytest.raises(ValueError, match="pricing"):
        budget.reserve({**request, "model": MODEL})
    with pytest.raises(RuntimeError, match="exhausted"):
        Budget(25.382478, prior=25.372478, model=SONNET).reserve(request)
    with pytest.raises(ValueError, match="Unsupported"):
        Budget(3, model="unknown")


@pytest.mark.anyio
@pytest.mark.parametrize("controls,case_id", [(False, None), (True, None), (False, "acceptance_h")])
async def test_single_arm_model_diagnostic_freezes_ten_reused_cases(
    tmp_path, monkeypatch, controls, case_id
):
    from simba_mcp.evaluation.hosts import __main__ as command
    from simba_mcp.evaluation.hosts.anthropic import SONNET
    from simba_mcp.guidance import read_guidance

    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "usage": {"input_tokens": 20, "output_tokens": 10},
                "content": [{"type": "text", "text": "{}"}],
                "stop_reason": "end_turn",
            },
        )

    monkeypatch.setattr(
        command, "client", lambda _: httpx.AsyncClient(transport=httpx.MockTransport(respond))
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-key")
    output = tmp_path / "diagnostic.json"
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                s: read_guidance("results", s)
                for s in ("entrypoint", "interpretation", "tool-reference")
            }
        )
    )
    await command.run(
        SimpleNamespace(
            output=output,
            cap_usd=3,
            prior_usd=0,
            samples=2,
            mode="eager",
            case=case_id,
            results_robust=True,
            results_model_diagnostic=True,
            model=SONNET,
            results_baseline=baseline if controls else None,
        )
    )
    report = json.loads(output.read_text())
    assert report["status"] == "complete"
    count = 2 if case_id else 14 if controls else 10
    assert len(report["trials"]) == len(requests) == count
    assert {r["case"] for r in report["trials"]} == (
        {case_id}
        if case_id
        else {
            "acceptance_a",
            "acceptance_d",
            "acceptance_e",
            "acceptance_f",
            "acceptance_h",
        }
    )
    assert sum(r["view"] == "candidate" for r in report["trials"]) == (2 if case_id else 10)
    assert {r["case"] for r in report["trials"] if r["view"] == "baseline"} == (
        {"acceptance_a", "acceptance_e"} if controls else set()
    )
    if controls:
        for rep in (0, 1):
            arms = [
                r["view"]
                for r in report["trials"]
                if r["case"] == "acceptance_a" and r["repetition"] == rep
            ]
            assert arms == (["baseline", "candidate"] if rep == 0 else ["candidate", "baseline"])
    assert all(r["thinking"] == {"type": "adaptive"} and "temperature" not in r for r in requests)
    assert report["experiment_inputs"]["purpose"] == "model_selection_validation"
    assert not report["assessment"]["accepted"]
    assert report["budget"]["charged"] == pytest.approx(count * 0.00014)


def test_format_failure_is_separate_from_correct_facts():
    assert answer('Here it is: ```json\n{"status":"pending"}\n```') == (
        {"status": "pending"},
        False,
    )
    assert answer('{"status":"pending"}') == ({"status": "pending"}, True)


@pytest.mark.anyio
async def test_fresh_packet_runs_only_frozen_paired_fresh_cases(tmp_path, monkeypatch):
    from simba_mcp.evaluation.hosts import __main__ as command
    from simba_mcp.evaluation.result_acceptance_fresh import fresh_acceptance_tasks
    from simba_mcp.guidance import read_guidance

    async def fake_session(*args, **kwargs):
        return {"final_text": "{}", "cost_usd": 0, "calls": [], "stop": "end_turn"}

    monkeypatch.setattr(command, "session", fake_session)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-key")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                s: read_guidance("results", s)
                for s in ("entrypoint", "interpretation", "tool-reference")
            }
        )
    )
    output = tmp_path / "fresh.json"
    await command.run(
        SimpleNamespace(
            output=output,
            cap_usd=0,
            prior_usd=0,
            samples=2,
            mode="eager",
            case=None,
            results_robust=True,
            results_acceptance=True,
            results_acceptance_packet="fresh",
            results_baseline=baseline,
            case_review={"verified": True, "guidance_unchanged": True},
        )
    )
    report = json.loads(output.read_text())
    assert len(report["trials"]) == 32
    assert {r["case"] for r in report["trials"]} == {t.id for t in fresh_acceptance_tasks()}
    assert report["configuration"]["results_acceptance_packet"] == "fresh"
    assert report["experiment_inputs"]["purpose"] == "candidate_acceptance"
    assert not report["assessment"]["accepted"]


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


@pytest.mark.anyio
async def test_role_selections_are_independent_and_data_scientist_is_full():
    from simba_mcp.profiles import PROFILES, select_tools
    from simba_mcp.server import create_server

    server = create_server("compact")
    tools = await server.list_tools()
    original = [tool.model_dump() for tool in tools]
    assert select_tools(tools, "data_scientist") == tools
    for role, names in PROFILES.items():
        selected = select_tools(tools, role)
        assert {tool.name for tool in selected} == names
        assert selected == [tool for tool in tools if tool.name in names]
        selected.clear()
        assert [tool.model_dump() for tool in await server.list_tools()] == original
    with pytest.raises(ValueError, match="Unknown"):
        select_tools(tools, "administrator")
    with pytest.raises(ValueError, match="missing tools"):
        select_tools([], "marketer")
    assert select_tools(tools, "full") == tools


@pytest.mark.anyio
async def test_all_role_jobs_execute_with_visible_tools_and_exact_mock_requests():
    from simba_mcp.evaluation.hosts.roles import ROLE_CASES
    from simba_mcp.evaluation.hosts.scenarios import SyntheticDispatch, role_tasks
    from simba_mcp.profiles import select_tools
    from simba_mcp.server import create_server

    server = create_server("compact")
    tools = await server.list_tools()
    suite = {case.id: case for case, _, _ in role_tasks()}
    for role, case_ids in ROLE_CASES.items():
        visible = {tool.name for tool in select_tools(tools, role)}
        for case_id in case_ids:
            case = suite[case_id]
            assert {step.tool for step in case.steps} <= visible
            dispatch = SyntheticDispatch(server, case, allowed_tools=visible)
            for step in case.steps:
                _, error = await dispatch(step.tool, step.arguments)
                assert error == step.is_error
            assert dispatch.completed == len(case.steps)
            assert dispatch.errors == dispatch.unintended_writes == 0


@pytest.mark.anyio
async def test_out_of_role_tool_needs_explicit_full_fallback_without_mutating_view():
    from simba_mcp.evaluation.cases import cases
    from simba_mcp.evaluation.hosts.scenarios import SyntheticDispatch
    from simba_mcp.profiles import select_tools
    from simba_mcp.server import create_server

    server = create_server("compact")
    tools = await server.list_tools()
    case = next(case for case in cases() if case.id == "advanced_priors")
    visible = {tool.name for tool in select_tools(tools, "marketer")}
    restricted = SyntheticDispatch(server, case, allowed_tools=visible)
    step = case.steps[0]
    payload, error = await restricted(step.tool, step.arguments)
    assert error and "full catalogue" in payload["error"]
    assert restricted.completed == 0
    fallback = SyntheticDispatch(
        server, case, allowed_tools=[tool.name for tool in select_tools(tools, "full")]
    )
    _, error = await fallback(step.tool, step.arguments)
    assert not error and fallback.completed == 1
    assert step.tool not in visible
    assert restricted.completed == 0


@pytest.mark.anyio
async def test_expected_backend_refusal_is_still_a_tool_error():
    from simba_mcp.evaluation.cases import cases
    from simba_mcp.evaluation.hosts.scenarios import SyntheticDispatch
    from simba_mcp.server import create_server

    case = next(case for case in cases() if case.id == "wrong_channel")
    dispatch = SyntheticDispatch(create_server("compact"), case)
    _, error = await dispatch(case.steps[0].tool, case.steps[0].arguments)
    assert error
    assert dispatch.completed == 1 and dispatch.errors == 0


@pytest.mark.anyio
async def test_role_cli_pairs_identical_tasks_and_alternates_order(tmp_path, monkeypatch):
    from simba_mcp.evaluation.hosts import __main__ as command

    requests = []

    def transport(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(body["messages"]) == 1:
            content = [
                {
                    "type": "tool_use",
                    "id": "status",
                    "name": "get_model_status",
                    "input": {"model_hash": "model-example"},
                },
                {
                    "type": "tool_use",
                    "id": "results",
                    "name": "get_model_results",
                    "input": {"model_hash": "model-example", "sections": "channel_summary"},
                },
            ]
            stop = "tool_use"
        else:
            content = [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "channel": "search_clicks",
                            "roi": 2.0,
                            "contribution_share": 0.1,
                            "unit": "units",
                            "interval": [0.05, 0.15],
                        }
                    ),
                }
            ]
            stop = "end_turn"
        return httpx.Response(
            200,
            json={
                "content": content,
                "stop_reason": stop,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    monkeypatch.setattr(
        command, "client", lambda _: httpx.AsyncClient(transport=httpx.MockTransport(transport))
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-test-key")
    output = tmp_path / "paired.json"
    await command.run(
        SimpleNamespace(
            output=output,
            cap_usd=10,
            prior_usd=7,
            case="analyse_model",
            mode="eager",
            samples=2,
            role_comparison="marketer",
        )
    )
    report = json.loads(output.read_text())
    assert [row["view"] for row in report["trials"]] == ["full", "marketer", "marketer", "full"]
    assert all(row["passed"] for row in report["trials"])
    assert len({json.dumps(r["messages"][0], sort_keys=True) for r in requests}) == 1
    assert requests[0]["tools"] == requests[-1]["tools"]
    assert len(requests[0]["tools"]) > len(requests[2]["tools"])
    assert report["budget"]["prior"] == 7
    assert report["budget"]["charged"] > 0 and report["budget"]["reserved"] == 0
