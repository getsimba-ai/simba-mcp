"""Agent contracts across metadata, backend discovery and uncertain writes."""

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import anyio
import httpx
import pytest
from jsonschema import validate

from simba_mcp import auth, server
from simba_mcp.api_client import CALLER_API_KEY, SimbaAPIClient
from simba_mcp.tools.capabilities import get_capabilities
from simba_mcp.tools.pagination import page


@pytest.fixture
def anyio_backend():
    return "asyncio"


def context(client, key=""):
    return SimpleNamespace(
        headers={"Authorization": f"Bearer {key}"},
        request_context=SimpleNamespace(lifespan_context=server.AppContext(client)),
    )


def test_metadata_covers_every_tool_and_mixed_actions_are_conservative():
    tools = {t.name: t for t in anyio.run(server.mcp.list_tools)}
    for tool in tools.values():
        assert tool.title and tool.annotations
        assert tool.annotations.open_world_hint is True
        assert tool.output_schema
    for name in ("adopt_model_into_study", "set_run_pinned", "evaluate_study_run"):
        assert tools[name].annotations.read_only_hint is False
        assert tools[name].annotations.idempotent_hint is False
    assert tools["delete_model"].annotations.destructive_hint is True
    assert tools["launch_study_run"].annotations.idempotent_hint is True
    assert tools["compare_study_runs"].annotations.read_only_hint is True


def test_old_calls_keep_types_required_arguments_and_defaults():
    baseline = json.loads(Path(__file__).with_name("legacy_input_contract.json").read_text())
    live = {t.name: t.input_schema for t in anyio.run(server.mcp.list_tools)}

    def strip(value):
        if isinstance(value, dict):
            return {k: strip(v) for k, v in value.items() if k not in ("description", "title")}
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value

    for name, old in baseline.items():
        new = strip(live[name])
        assert new.get("required", []) == old.get("required", [])
        for key, schema in old["properties"].items():
            assert new["properties"][key] == schema, (name, key)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "schema,status",
    [
        ({}, "unadvertised"),
        ({"x-simba-model-capabilities": []}, "unadvertised"),
        ({"error": "forbidden", "_status_code": 403}, "unavailable"),
    ],
)
async def test_legacy_and_failed_discovery_never_invent_support(schema, status, monkeypatch):
    monkeypatch.setattr(auth, "_serving_http", False)
    result = await get_capabilities(
        context(SimpleNamespace(get_schema=AsyncMock(return_value=schema)))
    )
    assert result.status == status
    assert result.advertised == {}
    assert set(result.unknown) == {
        "model_families",
        "transformations",
        "priors",
        "control_priors",
        "workflows",
    }


@pytest.mark.anyio
async def test_discovery_preserves_new_backend_fields_and_does_not_cache(monkeypatch):
    monkeypatch.setattr(auth, "_serving_http", True)
    seen = []

    async def respond(request):
        key = request.headers["Authorization"]
        seen.append(key)
        await asyncio.sleep(0)
        return httpx.Response(
            200,
            json={
                "x-simba-model-capabilities": {
                    "control_priors": {"version": 1, "transforms": ["LOG"]},
                    "future": key,
                }
            },
        )

    client = SimbaAPIClient("http://test", "")
    client._client = httpx.AsyncClient(
        base_url="http://test", transport=httpx.MockTransport(respond)
    )
    try:
        a, b = await asyncio.gather(
            get_capabilities(context(client, "a")), get_capabilities(context(client, "b"))
        )
        assert a.advertised["future"] == "Bearer a"
        assert b.advertised["future"] == "Bearer b"
        assert "transformations" in a.unknown
        assert len(seen) == 2
    finally:
        await client.close()


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["POST", "PATCH", "PUT", "DELETE"])
async def test_uncertain_writes_are_never_automatically_replayed(method, caplog):
    calls = []

    def respond(request):
        calls.append(request)
        raise httpx.ReadError("SECRET_TOKEN and confidential payload")

    client = SimbaAPIClient("http://test", "key")
    client._client = httpx.AsyncClient(
        base_url="http://test", transport=httpx.MockTransport(respond)
    )
    token = CALLER_API_KEY.set(None)
    try:
        result = await client._request(method, "/sensitive-object", json={"secret": "SECRET_TOKEN"})
        assert len(calls) == 1
        assert result["_mcp_error"]["transient"] is True
        assert result["_mcp_error"]["safe_to_retry"] is False
        assert "SECRET_TOKEN" not in json.dumps(result) + caplog.text
    finally:
        CALLER_API_KEY.reset(token)
        await client.close()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status,body", [(502, "<html>SECRET_TOKEN</html>"), (400, "[]"), (200, "bad json")]
)
async def test_malformed_backend_responses_are_safe(status, body):
    client = SimbaAPIClient("http://test", "key")
    client._client = httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(
            lambda req: httpx.Response(
                status, text=body, headers={"Content-Type": "application/json"}
            )
        ),
    )
    token = CALLER_API_KEY.set(None)
    try:
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.get_schema()
        assert result["_status_code"] >= 400
        assert "SECRET_TOKEN" not in json.dumps(result)
        assert result["_mcp_error"]["code"]
    finally:
        CALLER_API_KEY.reset(token)
        await client.close()


def test_paging_preserves_legacy_output_and_never_rewrites_evidence():
    payload = {"runs": [{"id": i, "future_field": True} for i in range(5)], "extra": 1}
    assert page(payload, "runs", None, 0) is payload
    result = page(payload, "runs", 2, 2)
    assert result["runs"] == payload["runs"][2:4]
    assert result["extra"] == 1
    assert result["_mcp_page"]["next_offset"] == 4
    assert result["_mcp_page"]["mode"] == "client_side"
    assert len(payload["runs"]) == 5
    assert page(payload, "runs", 201, 0)["_status_code"] == 400
    assert page(payload, "runs", 2, -1)["_status_code"] == 400


def test_discovery_wire_output_matches_advertised_schema(monkeypatch):
    from starlette.testclient import TestClient

    async def schema(self):
        return {"x-simba-model-capabilities": {"model_families": ["mmm"], "new_field": True}}

    monkeypatch.setattr(SimbaAPIClient, "get_schema", schema)
    monkeypatch.setattr(auth, "_serving_http", False)
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    with TestClient(server._create_app()) as client:
        result = client.post(
            "/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "get_capabilities", "arguments": {}},
            },
        ).json()["result"]
    tool = next(t for t in anyio.run(server.mcp.list_tools) if t.name == "get_capabilities")
    validate(result["structuredContent"], tool.output_schema)
    assert result["structuredContent"]["advertised"]["new_field"] is True
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]


@pytest.mark.anyio
async def test_real_stdio_handshake_discovery_and_missing_credentials():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "simba_mcp"],
        env={"SIMBA_API_KEY": "", "SIMBA_API_URL": "http://127.0.0.1:1"},
    )
    async with (
        stdio_client(params) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        initialized = await session.initialize()
        assert initialized.server_info.name == "Simba MMM"
        tools = await session.list_tools()
        assert "get_capabilities" in {tool.name for tool in tools.tools}
        result = await session.call_tool("get_capabilities", {})
        assert result.structured_content["status"] == "unavailable"
        assert result.structured_content["backend_error"]["_status_code"] == 401
