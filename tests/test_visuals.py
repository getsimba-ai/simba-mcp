"""Native visual tools preserve data and errors through the real MCP wire."""

import json
from importlib.resources import files

import anyio
import httpx
import pytest
from starlette.testclient import TestClient

from simba_mcp import runtime, server
from simba_mcp.api_client import SimbaAPIClient
from simba_mcp.visuals import RESOURCE_URI, VISUAL_TOOLS
from tests.test_wire_errors import _call


@pytest.mark.parametrize(
    "tool,section",
    [
        ("show_response_curves", "response_curves,mroi_summary,channel_map,model_config"),
        ("show_decomposition", "contributions,channel_map,model_config"),
        ("show_optimizer_allocation", None),
    ],
)
@pytest.mark.parametrize("status", [200, 403])
def test_visual_wire_is_read_only_passthrough(monkeypatch, tool, section, status):
    payload = (
        {"response_curves": [{"Spend": 1, "Search": None}]}
        if status == 200
        else {"error": "Refused"}
    )

    def handle(request):
        assert request.method == "GET"
        assert "prediction_window" not in str(request.url)
        if section:
            assert request.url.params["sections"] == section
        else:
            assert "saved-synthetic" in str(request.url)
        return httpx.Response(status, json=payload)

    async def get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://example.test", transport=httpx.MockTransport(handle)
            )
        return self._client

    monkeypatch.setattr(runtime, "_serving_http", runtime._serving_http)
    monkeypatch.setattr(SimbaAPIClient, "_get_client", get_client)
    with TestClient(server._create_app()) as client:
        arguments = {"model_hash": "synthetic"}
        if not section:
            arguments["run_id"] = "saved-synthetic"
        result = _call(client, tool, arguments)
    body = result["structuredContent"]
    if status == 200:
        assert body == payload
        assert not result.get("isError")
    else:
        assert body["error"] == "Refused"
        assert body["_status_code"] == 403
        assert result["isError"]
    assert json.loads(result["content"][0]["text"]) == body


def test_resource_and_only_visual_tools_advertise_apps():
    instance = server.create_server()
    tools = anyio.run(instance.list_tools)
    assert {t.name for t in tools if t.meta and "ui" in t.meta} == VISUAL_TOOLS
    for tool in tools:
        if tool.name in VISUAL_TOOLS:
            assert tool.annotations.read_only_hint
            assert tool.meta["ui"]["resourceUri"] == RESOURCE_URI
    resources = anyio.run(instance.list_resources)
    resource = next(r for r in resources if str(r.uri) == RESOURCE_URI)
    assert resource.mime_type == "text/html;profile=mcp-app"
    assert resource.meta["ui"]["csp"] == {}
    html = files("simba_mcp").joinpath("ui/charts.html").read_text(encoding="utf-8")
    assert len(html.encode()) <= 30_000
    assert "fetch(" not in html and "XMLHttpRequest" not in html
    assert "<script src=" not in html and "@import" not in html
