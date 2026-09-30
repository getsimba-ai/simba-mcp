"""Fixed profiles on real registrations, transports and isolated caller contexts."""

import asyncio
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import anyio
import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.mcpserver.exceptions import ToolError
from starlette.testclient import TestClient

from simba_mcp import runtime
from simba_mcp.api_client import CALLER_API_KEY
from simba_mcp.auth import _local_files_allowed
from simba_mcp.evaluation.cases import cases
from simba_mcp.evaluation.contracts import Case, Exchange, Step
from simba_mcp.evaluation.hosts.roles import ROLE_CASES
from simba_mcp.evaluation.hosts.scenarios import role_tasks
from simba_mcp.evaluation.runner import run_case
from simba_mcp.profiles import PROFILES, select_tools
from simba_mcp.server import create_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["legacy", "compact"])
async def test_profiles_preserve_exact_contracts_and_full_fallback(mode, monkeypatch):
    monkeypatch.setenv("SIMBA_TOOL_PROFILE", "marketer")
    full = create_server(mode)
    original = await full.list_tools()
    assert await create_server(mode, profile="data_scientist").list_tools() == original
    for role in PROFILES:
        instance = create_server(mode, profile=role)
        assert await instance.list_tools() == select_tools(original, role)
        with pytest.raises(ToolError):
            await instance.call_tool("create_model", {})
    assert await full.list_tools() == original
    with pytest.raises(ValueError, match="Unknown tool profile"):
        create_server(mode, profile="typo")
    trial = await run_case(next(c for c in cases() if c.id == "advanced_priors"), mcp_server=full)
    assert trial.passed


@pytest.mark.anyio
@pytest.mark.parametrize(
    "role,case",
    [
        (role, case)
        for role, names in ROLE_CASES.items()
        for case, _, _ in role_tasks()
        if case.id in names
    ],
    ids=lambda x: x if isinstance(x, str) else x.id,
)
async def test_registered_role_workflows(role, case):
    trial = await run_case(case, mcp_server=create_server("compact", profile=role))
    assert trial.passed, trial.assertions
    assert trial.unintended_writes == 0


@pytest.mark.anyio
@pytest.mark.parametrize("case", cases(), ids=lambda c: c.id)
async def test_data_scientist_retains_full_workflows(case):
    trial = await run_case(case, mcp_server=create_server(profile="data_scientist"))
    assert trial.passed, trial.assertions


@pytest.mark.anyio
async def test_mixed_transport_instances_and_callers_do_not_share_mode_or_credentials(monkeypatch):
    monkeypatch.setenv("SIMBA_API_KEY", "synthetic-stdio")
    monkeypatch.delenv("SIMBA_MCP_ALLOW_LOCAL_FILES", raising=False)
    local = create_server(profile="data_scientist")
    marketer = create_server(profile="marketer")
    reviewer = create_server(profile="reviewer")
    runtime.create_app(marketer)
    reviewer.sse_app()
    # Even legacy mode changes cannot alter an explicitly configured instance.
    monkeypatch.setattr(runtime, "_serving_http", True)

    async def handle(request):
        await asyncio.sleep(0)
        return httpx.Response(200, json={"caller": request.headers["authorization"]})

    async with (
        runtime.app_lifespan(local) as a,
        runtime.app_lifespan(marketer) as b,
        runtime.app_lifespan(reviewer) as c,
    ):
        assert [a.serving_http, b.serving_http, c.serving_http] == [False, True, True]
        assert [a.client._api_key, b.client._api_key, c.client._api_key] == [
            "synthetic-stdio",
            "",
            "",
        ]
        for app in (a, b, c):
            app.client._client = httpx.AsyncClient(
                base_url="https://example.invalid",
                headers=app.client._headers,
                transport=httpx.MockTransport(handle),
            )

        async def invoke(server, app, bearer):
            ctx = SimpleNamespace(
                headers={"Authorization": f"Bearer {bearer}"} if bearer else {},
                request_context=SimpleNamespace(lifespan_context=app),
            )
            assert _local_files_allowed(ctx) == (not app.serving_http)
            result = await server.call_tool("list_models", {}, ctx)
            assert CALLER_API_KEY.get() is None
            return result.structured_content

        token = CALLER_API_KEY.set(None)
        try:
            results = await asyncio.gather(
                invoke(local, a, "ignored"),
                invoke(marketer, b, "synthetic-A"),
                invoke(reviewer, c, "synthetic-B"),
                invoke(marketer, b, ""),
            )
            assert [r.get("caller") for r in results[:3]] == [
                "Bearer synthetic-stdio",
                "Bearer synthetic-A",
                "Bearer synthetic-B",
            ]
            assert results[3]["_status_code"] == 401
            assert "synthetic-stdio" not in json.dumps(results[1:])
        finally:
            CALLER_API_KEY.reset(token)


@pytest.mark.parametrize("profile", ["marketer", "reviewer", "full"])
def test_http_wire_profile_and_explicit_full_reconnection(profile, monkeypatch):
    from simba_mcp.api_client import SimbaAPIClient

    async def preference(self, method, path, **kwargs):
        assert path == "/api/v1/mcp/preferences"
        assert CALLER_API_KEY.get() == "synthetic-wire"
        return {"schema_version": 1, "profile": "full"}

    monkeypatch.setattr(SimbaAPIClient, "_request", preference)
    instance = create_server("compact", profile=profile)
    with TestClient(runtime.create_app(instance)) as client:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer synthetic-wire",
        }
        response = client.post(
            "/",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert response.status_code == 200
        names = {t["name"] for t in response.json()["result"]["tools"]}
        assert ("create_model" in names) == (profile == "full")
        if profile != "full":
            assert names == PROFILES[profile]
            refused = client.post(
                "/",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "create_model", "arguments": {}},
                },
            ).json()
            assert "error" in refused or refused.get("result", {}).get("isError")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "env_role,args,expected",
    [
        ("marketer", [], "marketer"),
        ("reviewer", ["--profile", "full"], "full"),
        ("full", ["--profile", "data_scientist"], "full"),
    ],
)
async def test_real_stdio_startup_role_and_cli_fallback(env_role, args, expected):
    with anyio.fail_after(30):
        async with (
            stdio_client(
                StdioServerParameters(
                    command=sys.executable,
                    args=["-m", "simba_mcp", *args],
                    env={
                        "SIMBA_TOOL_PROFILE": env_role,
                        "SIMBA_API_KEY": "",
                        "SIMBA_TOOL_DESCRIPTIONS": "compact",
                    },
                )
            ) as (read, write),
            ClientSession(read, write) as client,
        ):
            init = await client.initialize()
            names = {t.name for t in (await client.list_tools()).tools}
            if expected == "full":
                assert "create_model" in names and "launch_study_run" in names
            else:
                assert names == PROFILES[expected]
                assert "--profile full" in init.instructions
            response = await client.call_tool("get_backend_capabilities", {})
            assert response.structured_content["_status_code"] == 401


@pytest.mark.parametrize("env_role,args", [("typo", []), ("full", ["--profile", "typo"])])
def test_invalid_startup_fails_before_serving(env_role, args):
    result = subprocess.run(
        [sys.executable, "-m", "simba_mcp", *args],
        env={**os.environ, "SIMBA_TOOL_PROFILE": env_role},
        input="",
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode != 0
    assert "typo" in result.stderr
    assert result.stdout == ""


@pytest.mark.anyio
async def test_marketer_can_submit_retrieve_and_curate_a_scenario():
    rows = [{"Date": "2026-10-05", "search_clicks": 100}]
    run = {"run_id": "scn-example", "status": "complete"}
    path = "/api/v1/models/model-example/scenario"
    identity = {"model_hash": "model-example", "run_id": "scn-example"}
    steps = [
        Step(
            tool="run_scenario",
            arguments={"model_hash": "model-example", "scenario_data": rows},
            exchanges=[
                Exchange(
                    method="POST",
                    path=path,
                    body={"scenario_data": rows, "rebuild_model": True},
                    response={"run_id": "scn-example", "status": "pending"},
                )
            ],
            expected={"run_id": "scn-example"},
        ),
        Step(
            tool="get_scenario_results",
            arguments=identity,
            exchanges=[Exchange(method="GET", path=path + "/runs/scn-example", response=run)],
            expected=run,
        ),
        Step(
            tool="update_run",
            arguments={**identity, "artifact": "scenario", "name": "Reviewed plan"},
            exchanges=[
                Exchange(
                    method="PATCH",
                    path=path + "/runs/scn-example",
                    body={"name": "Reviewed plan"},
                    response={**run, "name": "Reviewed plan"},
                )
            ],
            expected={"name": "Reviewed plan"},
        ),
        Step(
            tool="set_run_pinned",
            arguments={**identity, "artifact": "scenario", "pinned": True},
            exchanges=[
                Exchange(
                    method="POST",
                    path=path + "/runs/scn-example/pin",
                    body={"pinned": True},
                    response={**run, "pinned": True},
                )
            ],
            expected={"pinned": True},
        ),
    ]
    trial = await run_case(
        Case(
            id="curate_scenario",
            purpose="Keep exact run identity through planning and curation",
            steps=steps,
        ),
        mcp_server=create_server(profile="marketer"),
    )
    assert trial.passed, trial.assertions


@pytest.mark.anyio
async def test_reviewer_recovers_stale_assessment_by_inspection_without_replaying_write():
    path = "/api/v1/study-runs/run-example/evaluations"
    preview = {"policy_id": "policy-example", "preview": True}
    write = {"policy_id": "policy-example", "expected_basis_hash": "old-basis"}
    steps = [
        Step(
            tool="evaluate_study_run",
            arguments={"run_id": "run-example", **preview},
            exchanges=[
                Exchange(
                    method="POST", path=path, body=preview, response={"basis_hash": "old-basis"}
                )
            ],
            expected={"basis_hash": "old-basis"},
        ),
        Step(
            tool="evaluate_study_run",
            arguments={"run_id": "run-example", **write},
            exchanges=[
                Exchange(
                    method="POST",
                    path=path,
                    body=write,
                    status=409,
                    response={"code": "stale_evidence", "error": "Evidence changed"},
                )
            ],
            expected={"_status_code": 409},
            is_error=True,
        ),
        Step(
            tool="evaluate_study_run",
            arguments={"run_id": "run-example", **preview},
            exchanges=[
                Exchange(
                    method="POST", path=path, body=preview, response={"basis_hash": "new-basis"}
                )
            ],
            expected={"basis_hash": "new-basis"},
        ),
    ]
    trial = await run_case(
        Case(
            id="stale_assessment",
            purpose="Inspect changed evidence before any new assessment",
            steps=steps,
        ),
        mcp_server=create_server(profile="reviewer"),
    )
    assert trial.passed, trial.assertions
    assert trial.backend_attempts == 3
