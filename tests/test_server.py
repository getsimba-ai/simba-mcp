"""Tests for the MCP server layer — tool registration, metadata, and lifespan."""

import os
from unittest.mock import patch

import pytest

from simba_mcp.server import AppContext, app_lifespan, mcp

EXPECTED_TOOLS = [
    "get_data_schema",
    "upload_data",
    "list_models",
    "create_model",
    "get_model_status",
    "get_model_results",
    "run_optimizer",
    "get_optimizer_results",
    "get_scenario_template",
    "run_scenario",
    "get_scenario_results",
]


class TestToolRegistration:
    def test_all_tools_registered(self):
        """All 11 expected tools are registered on the mcp instance."""
        registered = {t.name for t in mcp._tool_manager.list_tools()}
        assert registered == set(EXPECTED_TOOLS)

    def test_tool_count(self):
        """Exactly 11 tools are registered."""
        assert len(mcp._tool_manager.list_tools()) == 11

    def test_every_tool_has_description(self):
        """Every registered tool has a non-empty description."""
        for tool in mcp._tool_manager.list_tools():
            assert tool.description, f"Tool {tool.name!r} has no description"


class TestLifespan:
    @pytest.mark.anyio
    async def test_lifespan_creates_client(self):
        """The lifespan context manager yields an AppContext with a SimbaAPIClient."""
        env = {"SIMBA_API_URL": "http://test:9999", "SIMBA_API_KEY": "sk_test"}
        with patch.dict(os.environ, env):
            async with app_lifespan(mcp) as ctx:
                assert isinstance(ctx, AppContext)
                assert ctx.client.base_url == "http://test:9999"

    @pytest.mark.anyio
    async def test_lifespan_closes_client(self):
        """The client is closed when the lifespan exits."""
        env = {"SIMBA_API_URL": "http://test:9999", "SIMBA_API_KEY": "sk_test"}
        with patch.dict(os.environ, env):
            async with app_lifespan(mcp) as ctx:
                client = ctx.client
            assert client._client is None or client._client.is_closed

    @pytest.mark.anyio
    async def test_lifespan_warns_without_api_key(self, caplog):
        """A warning is logged when SIMBA_API_KEY is empty."""
        env = {"SIMBA_API_URL": "http://test:9999", "SIMBA_API_KEY": ""}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("SIMBA_API_KEY", None)
            async with app_lifespan(mcp) as ctx:
                assert ctx.client is not None
        assert any("SIMBA_API_KEY" in r.message for r in caplog.records)
