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
        """A warning is logged when SIMBA_API_KEY is empty, with booking link."""
        env = {"SIMBA_API_URL": "http://test:9999", "SIMBA_API_KEY": ""}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("SIMBA_API_KEY", None)
            async with app_lifespan(mcp) as ctx:
                assert ctx.client is not None
        warnings = [r.message for r in caplog.records if "SIMBA_API_KEY" in r.message]
        assert len(warnings) == 1
        assert "calendly.com" in warnings[0]


class TestRunOptimizerPayload:
    """Payload construction for run_optimizer, incl. profit objective (issue #11)."""

    LEGACY_ARGS = dict(
        model_hash="abc123",
        total_budget=1_000_000.0,
        num_periods=4,
        gamma=0.0,
        currency="USD",
        bounds={"TV": {"lower": 0, "upper": 40}},
        laydown_weights={"TV": [1, 1, 1, 1]},
        period_cpm={"TV": [10.0, 10.0, 10.0, 10.0]},
    )

    def _ctx_capturing(self):
        """A fake Context whose client records the payload passed to run_optimizer."""
        from unittest.mock import AsyncMock, MagicMock

        client = MagicMock()
        client.run_optimizer = AsyncMock(return_value={"optimizer_status": "pending"})
        ctx = MagicMock()
        ctx.request_context.lifespan_context.client = client
        return ctx, client

    @pytest.mark.anyio
    async def test_legacy_args_produce_legacy_payload(self):
        """Backward compat: without new params the payload has exactly the 7 legacy keys."""
        from simba_mcp.server import run_optimizer

        ctx, client = self._ctx_capturing()
        await run_optimizer(**self.LEGACY_ARGS, ctx=ctx)
        _, payload = client.run_optimizer.call_args.args
        assert set(payload) == {
            "total_budget", "num_periods", "gamma", "currency",
            "bounds", "laydown_weights", "period_cpm",
        }

    @pytest.mark.anyio
    async def test_profit_objective_passthrough(self):
        from simba_mcp.server import run_optimizer

        ctx, client = self._ctx_capturing()
        await run_optimizer(**self.LEGACY_ARGS, objective="profit",
                            forward_margin=0.18, ctx=ctx)
        _, payload = client.run_optimizer.call_args.args
        assert payload["objective"] == "profit"
        assert payload["forward_margin"] == 0.18

    @pytest.mark.anyio
    async def test_period_multiplier_and_flags_passthrough(self):
        from simba_mcp.server import run_optimizer

        ctx, client = self._ctx_capturing()
        await run_optimizer(**self.LEGACY_ARGS, period_multiplier=[1.5] * 4,
                            include_historical_effect=False,
                            enable_warm_start=False, ctx=ctx)
        _, payload = client.run_optimizer.call_args.args
        assert payload["period_multiplier"] == [1.5] * 4
        assert payload["include_historical_effect"] is False
        assert payload["enable_warm_start"] is False

    @pytest.mark.anyio
    async def test_default_flags_not_sent(self):
        """True defaults for the booleans are omitted, not serialized as True."""
        from simba_mcp.server import run_optimizer

        ctx, client = self._ctx_capturing()
        await run_optimizer(**self.LEGACY_ARGS, objective="revenue", ctx=ctx)
        _, payload = client.run_optimizer.call_args.args
        assert "objective" not in payload
        assert "include_historical_effect" not in payload
        assert "enable_warm_start" not in payload
