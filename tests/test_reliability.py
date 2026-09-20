"""Regression coverage for public metadata, forward compatibility and retry safety."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import anyio
import anyio.lowlevel
import httpx
import pytest
from starlette.testclient import TestClient

from simba_mcp import runtime, server
from simba_mcp.api_client import SimbaAPIClient
from simba_mcp.metadata import annotations_for
from simba_mcp.tools.data import get_backend_capabilities
from simba_mcp.tools.results import get_model_results


def context(client):
    return SimpleNamespace(
        headers={}, request_context=SimpleNamespace(lifespan_context=runtime.AppContext(client))
    )


def test_metadata_effects_are_explicit():
    tools = {t.name: t for t in anyio.run(server.mcp.list_tools)}
    for name in (
        "get_model_results",
        "compare_study_runs",
        "assess_study_validation_pair",
        "list_study_evaluations",
    ):
        assert not tools[name].annotations.read_only_hint
        assert not tools[name].annotations.destructive_hint
        assert not tools[name].annotations.idempotent_hint
    assert all(t.title and t.annotations.open_world_hint for t in tools.values())
    for name in ("get_study_prediction_access", "validate_study_recipe", "get_scenario_template"):
        assert tools[name].annotations.read_only_hint
    for name in ("evaluate_study_run", "adopt_model_into_study"):
        assert not tools[name].annotations.read_only_hint
        assert not tools[name].annotations.idempotent_hint
    assert tools["launch_study_run"].annotations.idempotent_hint
    assert tools["save_model"].annotations.destructive_hint
    assert tools["delete_model"].annotations.destructive_hint
    assert tools["set_run_pinned"].annotations.idempotent_hint
    with pytest.raises(ValueError):
        annotations_for("unclassified_new_tool")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "schema,expected_unknown",
    [
        ({}, ["x-simba-model-capabilities", "x-simba-workflow-capabilities"]),
        (
            {"x-simba-model-capabilities": {"control_priors": {"version": 1}, "future": 7}},
            ["x-simba-workflow-capabilities"],
        ),
        (
            {"x-simba-model-capabilities": [], "x-simba-workflow-capabilities": {"version": 1}},
            ["x-simba-model-capabilities"],
        ),
    ],
)
async def test_discovery_never_invents_support(schema, expected_unknown):
    client = SimpleNamespace(get_schema=AsyncMock(return_value=schema))
    result = await get_backend_capabilities(context(client))
    assert result["unknown"] == expected_unknown
    for key, value in result["advertisements"].items():
        assert value == schema[key]


@pytest.mark.anyio
async def test_discovery_does_not_hide_auth_failure():
    error = {"error": "denied", "_status_code": 403}
    client = SimpleNamespace(get_schema=AsyncMock(return_value=error))
    assert await get_backend_capabilities(context(client)) == error


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["POST", "PATCH", "PUT", "DELETE"])
@pytest.mark.parametrize("failure", ["status", "transport"])
async def test_uncertain_writes_are_never_replayed(method, failure, monkeypatch, caplog):
    calls = []

    def handle(req):
        calls.append(req)
        if failure == "transport":
            raise httpx.ReadError("secret-key private payload https://user:password@host")
        return httpx.Response(503, json={"error": "busy"})

    client = SimbaAPIClient("http://test", "test-key")
    client._client = httpx.AsyncClient(
        base_url="http://test", transport=httpx.MockTransport(handle)
    )
    result = await client._request(method, "/api/v1/secret-user-object", json={"secret": "payload"})
    await client.close()
    assert len(calls) == 1
    assert result["_status_code"] == 503
    assert "submission key" in result["_next_action"]
    assert "secret" not in caplog.text
    assert "private payload" not in json.dumps(result)


@pytest.mark.anyio
async def test_read_retry_logging_redacts_path_and_exception(monkeypatch, caplog):
    monkeypatch.setattr("simba_mcp.api_client.asyncio.sleep", AsyncMock())

    def handle(req):
        raise httpx.ConnectError("credential and private payload")

    client = SimbaAPIClient("http://test", "credential")
    client._client = httpx.AsyncClient(
        base_url="http://test", transport=httpx.MockTransport(handle)
    )
    result = await client._request("GET", "/private-object")
    await client.close()
    assert "3 attempts" in result["error"]
    assert "credential" not in caplog.text + result["error"]
    assert "private" not in caplog.text + result["error"]


@pytest.mark.anyio
@pytest.mark.parametrize("status,payload", [(400, []), (502, "private gateway body"), (200, [])])
async def test_malformed_backend_payloads_have_actionable_errors(status, payload):
    client = SimbaAPIClient("http://test", "key")
    result = await client._parse_response(httpx.Response(status, json=payload))
    assert result["_status_code"] >= 400
    assert result["_next_action"]
    assert "private gateway body" not in json.dumps(result)


@pytest.mark.anyio
async def test_result_bound_preserves_full_default_and_refuses_partial_evidence():
    payload = {"results": {"future_section": ["evidence"] * 100}, "future_metadata": {"a": 1}}
    client = SimpleNamespace(get_model_results=AsyncMock(return_value=payload))
    ctx = context(client)
    assert await get_model_results("hash", ctx=ctx) == payload
    small = await get_model_results("hash", max_response_bytes=20, ctx=ctx)
    assert small["_status_code"] == 413
    assert "results" not in small
    assert await get_model_results("hash", max_response_bytes=10000, ctx=ctx) == payload


def test_structured_wire_outputs_preserve_unknown_fields_and_input_objects(monkeypatch):
    monkeypatch.setattr(runtime, "_serving_http", runtime._serving_http)
    captured = []
    response = {
        "id": "new",
        "future_evidence": {"unavailable": None},
        "fit_liveness": {"future": 1},
    }

    def handle(req):
        captured.append(json.loads(req.content))
        return httpx.Response(200, json=response)

    async def get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="http://test", transport=httpx.MockTransport(handle)
            )
        return self._client

    monkeypatch.setattr(SimbaAPIClient, "_get_client", get_client)
    with TestClient(server._create_app()) as client:
        result = client.post(
            "/",
            headers={
                "Accept": "application/json, text/event-stream",
                "Authorization": "Bearer caller",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "validate_study_recipe",
                    "arguments": {
                        "specification": {"kind": "future", "future_field": {"nested": 1}}
                    },
                },
            },
        ).json()["result"]
    assert not result.get("isError", False)
    assert result["structuredContent"] == response
    assert json.loads(result["content"][0]["text"]) == response
    assert captured == [{"specification": {"kind": "future", "future_field": {"nested": 1}}}]


def test_schema_describes_workflow_without_dropping_unknown_fields():
    tools = {t.name: t for t in anyio.run(server.mcp.list_tools)}
    recipe = tools["create_study_recipe"].input_schema["properties"]["specification"]
    assert recipe["required"] == ["kind"]
    assert recipe.get("additionalProperties") is not False
    assert (
        "maximum"
        in tools["create_quality_policy"].input_schema["properties"]["checks"]["items"][
            "properties"
        ]
    )
    assert tools["get_model_status"].output_schema["additionalProperties"]


@pytest.mark.anyio
async def test_real_stdio_handshake_and_structured_auth_error():
    import sys

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    with anyio.fail_after(20):
        async with (
            stdio_client(
                StdioServerParameters(
                    command=sys.executable,
                    args=["-m", "simba_mcp"],
                    env={"SIMBA_API_KEY": "", "SIMBA_API_URL": "http://127.0.0.1:1"},
                )
            ) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()
            assert len(tools.tools) == len(server.TOOLS)
            result = await session.call_tool("get_backend_capabilities", {})
            assert result.structured_content["_status_code"] == 401


@pytest.mark.anyio
async def test_recipe_hash_guard_is_forwarded_only_when_supplied():
    from simba_mcp.tools.recipes import create_study_recipe, revise_study_recipe

    client = SimpleNamespace(workflow_request=AsyncMock(return_value={"id": "revision"}))
    ctx = context(client)
    await create_study_recipe("study", "name", "reason", {"kind": "api_mmm"}, ctx=ctx)
    assert "expected_content_hash" not in client.workflow_request.call_args.args[2]
    await revise_study_recipe(
        "recipe", 2, "name", "reason", {"kind": "api_mmm"}, expected_content_hash="a" * 64, ctx=ctx
    )
    assert client.workflow_request.call_args.args[2]["expected_content_hash"] == "a" * 64
    assert client.workflow_request.call_args.args[2]["expected_version"] == 2


@pytest.mark.anyio
async def test_discovery_isolated_for_concurrent_hosted_callers(monkeypatch):
    from simba_mcp.api_client import CALLER_API_KEY

    monkeypatch.setattr(runtime, "_serving_http", True)

    async def handle(req):
        await anyio.lowlevel.checkpoint()
        return httpx.Response(
            200, json={"x-simba-model-capabilities": {"caller": req.headers["authorization"]}}
        )

    client = SimbaAPIClient("http://test", "")
    client._client = httpx.AsyncClient(
        base_url="http://test", transport=httpx.MockTransport(handle)
    )
    results = {}

    async def call(key):
        ctx = context(client)
        ctx.headers = {"Authorization": f"Bearer {key}"} if key else {}
        results[key] = await get_backend_capabilities(ctx)

    token = CALLER_API_KEY.set(None)
    try:
        async with anyio.create_task_group() as group:
            for key in ("one", "two", ""):
                group.start_soon(call, key)
        assert (
            results["one"]["advertisements"]["x-simba-model-capabilities"]["caller"] == "Bearer one"
        )
        assert (
            results["two"]["advertisements"]["x-simba-model-capabilities"]["caller"] == "Bearer two"
        )
        assert results[""]["_status_code"] == 401
        assert CALLER_API_KEY.get() is None
    finally:
        CALLER_API_KEY.reset(token)
        await client.close()


@pytest.mark.parametrize(
    "status,code",
    [
        (402, "entitlement_required"),
        (405, "unsupported_operation"),
        (413, "payload_too_large"),
        (422, "invalid_request"),
    ],
)
def test_client_failures_are_not_misreported_as_backend_outages(status, code):
    from simba_mcp.errors import api_error

    result = api_error(status, {"error": "original backend detail", "future": 3})
    assert result["_error_code"] == code
    assert result["error"] == "original backend detail"
    assert result["future"] == 3


@pytest.mark.anyio
async def test_prediction_window_export_preserves_evidence_and_section_request():
    rows = [{"date": "2026-01-08", "fit actual": 100, "model": 90}]
    payload = {"results": {"prediction_window": rows}}
    client = SimpleNamespace(get_model_results=AsyncMock(return_value=payload))
    result = await get_model_results(
        "hash",
        sections="prediction_window",
        channels=["tv"],
        max_grid_points=2,
        ctx=context(client),
    )
    assert result["results"]["prediction_window"] == rows
    client.get_model_results.assert_awaited_once_with(
        "hash", sections="prediction_window", fmt="json"
    )
