"""Draft payloads and backend conflicts survive the actual MCP transport."""

import json

import httpx
import pytest
from starlette.testclient import TestClient

from simba_mcp import runtime, server
from simba_mcp.api_client import SimbaAPIClient


@pytest.mark.parametrize("operation", ["create", "update", "get", "list", "template"])
def test_authoring_snapshot_crosses_wire_without_losing_fields(monkeypatch, operation):
    snapshot = {
        "schema_version": 1,
        "family": "var",
        "configuration": {
            "totalConfigurationData": {
                "sampler": "nutpie",
                "target_accept": 0.97,
                "future_field": {"keep": [1, 2, 3]},
                "priors_table": [{"halfLifeLower": "2.5"}],
            }
        },
        "model_setup": {"var_lags": 9},
        "model_details": {"costMode": "high"},
        "transformations": {},
        "source": {
            "name": "synthetic.csv",
            "content_base64": "YSxiCg==",
            "origin": {"kind": "uploaded_file", "id": 7, "sha256": "a" * 64},
        },
    }
    draft = {"id": "d1", "study_id": "s1", "version": 2, "snapshot": snapshot}
    cases = {
        "create": (
            "create_recipe_draft",
            "POST",
            "/studies/s1/recipe-drafts",
            {"study_id": "s1", "draft_id": "d1", "name": "Draft", "snapshot": snapshot},
        ),
        "update": (
            "update_recipe_draft",
            "PATCH",
            "/recipe-drafts/d1",
            {"draft_id": "d1", "name": "Draft", "snapshot": snapshot, "expected_version": 1},
        ),
        "get": ("get_recipe_draft", "GET", "/recipe-drafts/d1", {"draft_id": "d1"}),
        "list": ("list_recipe_drafts", "GET", "/studies/s1/recipe-drafts", {"study_id": "s1"}),
        "template": (
            "get_recipe_draft_template",
            "GET",
            "/recipe-draft-template",
            {"family": "var", "uploaded_file_id": 7},
        ),
    }
    tool, method, path, arguments = cases[operation]
    response = {"drafts": [{"id": "d1", "version": 2}]} if operation == "list" else draft
    if operation == "template":
        response = {"snapshot": snapshot, "template_hash": "abc", "publication_available": False}

    def handle(request):
        assert request.method == method
        assert request.url.path.endswith(path)
        if operation == "template":
            assert request.url.params["family"] == "var"
            assert request.url.params["uploaded_file_id"] == "7"
        if method in ("POST", "PATCH"):
            body = json.loads(request.content)
            assert body["snapshot"] == snapshot
            assert body.get("id") == ("d1" if method == "POST" else None)
            assert body.get("expected_version") == (1 if method == "PATCH" else None)
        return httpx.Response(200, json=response)

    async def get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="http://test", transport=httpx.MockTransport(handle)
            )
        return self._client

    monkeypatch.setattr(runtime, "_serving_http", runtime._serving_http)
    monkeypatch.setattr(SimbaAPIClient, "_get_client", get_client)
    with TestClient(server._create_app()) as client:
        result = client.post(
            "/",
            headers={
                "Accept": "application/json, text/event-stream",
                "Authorization": "Bearer synthetic-test-key",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            },
        ).json()["result"]
    assert not result.get("isError", False)
    assert result["structuredContent"] == response
