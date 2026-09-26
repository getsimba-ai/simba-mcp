"""Draft payloads and backend conflicts survive the actual MCP transport."""

import json

import httpx
import pytest
from starlette.testclient import TestClient

from simba_mcp import runtime, server
from simba_mcp.api_client import SimbaAPIClient


@pytest.mark.parametrize(
    "operation",
    [
        "create",
        "create_target",
        "update",
        "get",
        "list",
        "template",
        "pipeline_template",
        "publish",
        "publish_target",
        "authoring",
        "diff",
    ],
)
@pytest.mark.parametrize("edited", [False, True])
def test_authoring_snapshot_crosses_wire_without_losing_fields(monkeypatch, operation, edited):
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
    if operation == "pipeline_template":
        snapshot["source"]["origin"] = {
            "kind": "pipeline_version",
            "id": 9,
            "pipeline_id": 2,
            "version": 3,
            "sha256": "a" * 64,
        }
    if edited:
        snapshot["calibration_import"] = {
            "name": "experiment.json",
            "content_base64": "eyJsaWZ0VGVzdERhdGEiOltdfQ==",
            "sha256": "a" * 64,
        }
        snapshot["source"].pop("origin", None)
        snapshot["source"]["history"] = [
            {
                "kind": "remove_column",
                "column": "unused",
                "input_sha256": "a" * 64,
                "output_sha256": "b" * 64,
                "row_count": 2,
            }
        ]
    draft = {"id": "d1", "study_id": "s1", "version": 2, "snapshot": snapshot}
    cases = {
        "create": (
            "create_recipe_draft",
            "POST",
            "/studies/s1/recipe-drafts",
            {
                "study_id": "s1",
                "draft_id": "d1",
                "name": "Draft",
                "snapshot": snapshot,
                "source_revision_id": "source-revision",
            },
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
    cases["pipeline_template"] = (
        "get_recipe_draft_template",
        "GET",
        "/recipe-draft-template",
        {"family": "var", "pipeline_version_id": 9},
    )
    cases["publish"] = (
        "publish_recipe_draft",
        "POST",
        "/recipe-drafts/d1/publish",
        {
            "draft_id": "d1",
            "expected_version": 2,
            "publication_id": "p1",
            "reason": "Freeze this approach",
        },
    )
    cases["authoring"] = (
        "get_recipe_revision_authoring",
        "GET",
        "/recipes/r1/revisions/1/authoring",
        {"recipe_id": "r1", "number": 1},
    )
    # #884: an edit session names its recipe; publishing with a target writes revision N+1.
    cases["create_target"] = (
        "create_recipe_draft",
        "POST",
        "/studies/s1/recipe-drafts",
        {
            "study_id": "s1",
            "draft_id": "d1",
            "name": "Draft",
            "snapshot": snapshot,
            "target": {"recipe_id": "r1", "base_revision_id": "rev1"},
        },
    )
    cases["publish_target"] = (
        "publish_recipe_draft",
        "POST",
        "/recipe-drafts/d1/publish",
        {
            "draft_id": "d1",
            "expected_version": 2,
            "publication_id": "p1",
            "reason": "Tighten the TV prior",
            "target": {"recipe_id": "r1", "expected_version": 3},
        },
    )
    cases["diff"] = (
        "diff_recipe_revisions",
        "GET",
        "/recipes/r1/revisions/1/diff/2",
        {"recipe_id": "r1", "base": 1, "other": 2},
    )
    tool, method, path, arguments = cases[operation]
    response = {"drafts": [{"id": "d1", "version": 2}]} if operation == "list" else draft
    if operation in ("template", "pipeline_template"):
        response = {"snapshot": snapshot, "template_hash": "abc", "publication_available": False}
    if operation == "diff":
        response = {
            "base": {"number": 1, "id": "rev1"},
            "other": {"number": 2, "id": "rev2"},
            "settings": [
                {
                    "key": "adstock_type",
                    "label": "Adstock type",
                    "from": "geometric",
                    "to": "delayed",
                }
            ],
            "priors": [],
            "data": None,
            "counts": {"settings": 1, "priors": 0, "data": 0, "total": 1},
        }
    if operation in ("publish", "publish_target"):
        response = {
            "revisions": [
                {
                    "id": "r1",
                    "effective": {
                        "provenance": {
                            "calibration": {
                                "kind": "likelihood_observations",
                                "count": 1,
                                "units": "response",
                                "channels": ["tv"],
                                "content_hash": "abc",
                            }
                        }
                    },
                }
            ]
        }

    def handle(request):
        if operation == "create":
            body = json.loads(request.content)
            assert body["source_revision_id"] == "source-revision"
            assert "target" not in body  # omitted, not null: the wire is unchanged without it
        if operation == "create_target":
            body = json.loads(request.content)
            assert body["target"] == {"recipe_id": "r1", "base_revision_id": "rev1"}
            assert "source_revision_id" not in body
        assert request.method == method
        assert request.url.path.endswith(path)
        if operation in ("template", "pipeline_template"):
            assert request.url.params["family"] == "var"
            key, value = (
                ("uploaded_file_id", "7")
                if operation == "template"
                else ("pipeline_version_id", "9")
            )
            assert request.url.params[key] == value
        if operation == "publish":
            assert json.loads(request.content) == {
                "expected_version": 2,
                "publication_id": "p1",
                "reason": "Freeze this approach",
            }
        elif operation == "publish_target":
            assert json.loads(request.content) == {
                "expected_version": 2,
                "publication_id": "p1",
                "reason": "Tighten the TV prior",
                "target": {"recipe_id": "r1", "expected_version": 3},
            }
        elif method in ("POST", "PATCH"):
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
