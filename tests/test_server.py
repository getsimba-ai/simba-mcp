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


class TestGetModelResultsFiltering:
    """Channel filtering, grid downsampling, and csv format (issue #13)."""

    @staticmethod
    def _payload():
        curve_row = lambda i: {  # noqa: E731
            "Spend": float(i),
            "tv_activity": i * 1.0, "tv_activity_lower": i * 0.8,
            "tv_activity_upper_50": i * 1.1,
            "search_activity": i * 2.0, "search_activity_lower": i * 1.6,
        }
        return {
            "model_hash": "abc",
            "sections_available": ["response_curves"],
            "results": {
                "response_curves": [curve_row(i) for i in range(100)],
                "marginal_curves": [curve_row(i) for i in range(100)],
                "decay_curves": {"tv_activity": {"mean": 0.5},
                                 "search_activity": {"mean": 0.4}},
                "saturation": {"saturation_type": "tanh",
                               "channels": {"tv_activity": {}, "search_activity": {}}},
                "channel_summary": [{"Channel": "tv_activity", "ROI": 2.0},
                                    {"Channel": "search_activity", "ROI": 5.0}],
                "coefficients": [{"Channel": "tv_activity"},
                                 {"Channel": "search_activity"}],
                "mroi_summary": {"channels": [{"channel": "tv_activity"},
                                              {"channel": "search_activity"}]},
                "contributions": [{"Date": 1, "tv_activity": 1.0,
                                   "category_trend": 2.0, "Base": 3.0}],
            },
        }

    def _ctx_returning(self, payload):
        from unittest.mock import AsyncMock, MagicMock

        client = MagicMock()
        client.get_model_results = AsyncMock(return_value=payload)
        ctx = MagicMock()
        ctx.request_context.lifespan_context.client = client
        return ctx, client

    @pytest.mark.anyio
    async def test_channel_filter_applies_across_sections(self):
        from simba_mcp.server import get_model_results

        ctx, _ = self._ctx_returning(self._payload())
        res = await get_model_results("abc", channels=["search"], ctx=ctx)
        r = res["results"]
        assert set(r["response_curves"][0]) == {"Spend", "search_activity",
                                                "search_activity_lower"}
        assert list(r["decay_curves"]) == ["search_activity"]
        assert list(r["saturation"]["channels"]) == ["search_activity"]
        assert r["saturation"]["saturation_type"] == "tanh"  # non-channel keys kept
        assert [row["Channel"] for row in r["channel_summary"]] == ["search_activity"]
        assert [row["Channel"] for row in r["coefficients"]] == ["search_activity"]
        assert [row["channel"] for row in r["mroi_summary"]["channels"]] == ["search_activity"]

    @pytest.mark.anyio
    async def test_contributions_never_filtered(self):
        from simba_mcp.server import get_model_results

        ctx, _ = self._ctx_returning(self._payload())
        res = await get_model_results("abc", channels=["search"], ctx=ctx)
        assert set(res["results"]["contributions"][0]) == {
            "Date", "tv_activity", "category_trend", "Base",
        }

    @pytest.mark.anyio
    async def test_grid_downsampling_keeps_endpoints(self):
        from simba_mcp.server import get_model_results

        ctx, _ = self._ctx_returning(self._payload())
        res = await get_model_results("abc", max_grid_points=10, ctx=ctx)
        recs = res["results"]["response_curves"]
        assert len(recs) == 10
        assert recs[0]["Spend"] == 0.0
        assert recs[-1]["Spend"] == 99.0
        spends = [r["Spend"] for r in recs]
        assert spends == sorted(spends)

    @pytest.mark.anyio
    async def test_no_new_params_passthrough_unchanged(self):
        from simba_mcp.server import get_model_results

        payload = self._payload()
        ctx, client = self._ctx_returning(payload)
        res = await get_model_results("abc", sections="channel_summary", ctx=ctx)
        assert res is payload  # untouched object
        assert client.get_model_results.call_args.kwargs["fmt"] == "json"

    @pytest.mark.anyio
    async def test_csv_format_passthrough(self):
        from simba_mcp.server import get_model_results

        csv_res = {"format": "csv", "content": "# channel_summary\na,b\n"}
        ctx, client = self._ctx_returning(csv_res)
        res = await get_model_results("abc", format="csv", channels=["search"], ctx=ctx)
        assert res is csv_res  # filtering skipped for csv
        assert client.get_model_results.call_args.kwargs["fmt"] == "csv"

    @pytest.mark.anyio
    async def test_error_payload_not_filtered(self):
        from simba_mcp.server import get_model_results

        err = {"error": "nope", "_status_code": 404}
        ctx, _ = self._ctx_returning(err)
        res = await get_model_results("abc", channels=["search"], ctx=ctx)
        assert res is err

    def test_channel_name_normalization(self):
        from simba_mcp.server import _column_channel, _norm_channel

        assert _norm_channel("Search_Activity") == "search"
        assert _norm_channel("search") == "search"
        assert _norm_channel("Digital impressions") == "digital_impressions"
        assert _column_channel("search_activity_lower_50") == "search"
        assert _column_channel("search_activity_upper") == "search"
