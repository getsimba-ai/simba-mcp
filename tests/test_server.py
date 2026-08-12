"""Tests for the MCP server layer — tool registration, metadata, and lifespan."""

import os
from typing import ClassVar
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


class TestResultsSectionsDoc:
    """Guard against the get_model_results section list going stale (issue #12)."""

    # Every section the API's results endpoint can serve must be discoverable
    # from the tool description — for agent-driven use the docstring IS the API.
    API_SECTIONS: ClassVar[list[str]] = [
        "channel_summary",
        "contributions",
        "coefficients",
        "params",
        "decay_curves",
        "response_curves",
        "marginal_curves",
        "saturation",
        "mroi_summary",
        "model_stats",
        "actual_vs_model",
        "long_run_rollup",
        "optimizer",
        "predictions",
        "posterior",
        "financials",
        "model_config",
    ]

    def _description(self, name):
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == name)
        return tool.description

    def test_all_sections_documented(self):
        """Require the bullet form `- section_name:` so a name mentioned in
        passing (e.g. 'optimizer' inside another sentence) doesn't false-pass."""
        desc = self._description("get_model_results")
        missing = [s for s in self.API_SECTIONS if f"- {s}:" not in desc]
        assert not missing, (
            f"Sections missing as `- name:` bullets from get_model_results docstring: {missing}"
        )

    def test_activity_column_naming_rule_documented(self):
        """The activity-column key rule must appear in every tool that consumes
        channel keys."""
        for name in ("get_model_results", "run_optimizer", "run_scenario"):
            desc = self._description(name)
            assert "activity" in desc.lower() and "channels[].name" in desc, (
                f"{name} docstring must state that results/template keys are the "
                "activity-column names, not channels[].name"
            )


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

    LEGACY_ARGS: ClassVar[dict] = {
        "model_hash": "abc123",
        "total_budget": 1_000_000.0,
        "num_periods": 4,
        "gamma": 0.0,
        "currency": "USD",
        "bounds": {"TV": {"lower": 0, "upper": 40}},
        "laydown_weights": {"TV": [1, 1, 1, 1]},
        "period_cpm": {"TV": [10.0, 10.0, 10.0, 10.0]},
    }

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
            "total_budget",
            "num_periods",
            "gamma",
            "currency",
            "bounds",
            "laydown_weights",
            "period_cpm",
        }

    @pytest.mark.anyio
    async def test_profit_objective_passthrough(self):
        from simba_mcp.server import run_optimizer

        ctx, client = self._ctx_capturing()
        await run_optimizer(**self.LEGACY_ARGS, objective="profit", forward_margin=0.18, ctx=ctx)
        _, payload = client.run_optimizer.call_args.args
        assert payload["objective"] == "profit"
        assert payload["forward_margin"] == 0.18

    @pytest.mark.anyio
    async def test_period_multiplier_and_flags_passthrough(self):
        from simba_mcp.server import run_optimizer

        ctx, client = self._ctx_capturing()
        await run_optimizer(
            **self.LEGACY_ARGS,
            period_multiplier=[1.5] * 4,
            include_historical_effect=False,
            enable_warm_start=False,
            ctx=ctx,
        )
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


class TestCreateModelPayload:
    """Payload construction for create_model architecture params
    (saturation_type / transform_order / link)."""

    BASE_ARGS: ClassVar[dict] = {
        "uploaded_file_id": 7,
        "date_column": "date",
        "kpi_column": "sales",
        "hierarchy_column": "brand",
        "channels": [{"name": "TV", "activity_column": "tv_activity", "spend_column": "tv_spend"}],
    }

    def _ctx_capturing(self):
        from unittest.mock import AsyncMock, MagicMock

        client = MagicMock()
        client.create_model = AsyncMock(return_value={"model_hash": "h"})
        ctx = MagicMock()
        ctx.request_context.lifespan_context.client = client
        return ctx, client

    @pytest.mark.anyio
    async def test_default_config_unchanged(self):
        """Defaults keep the config byte-identical to pre-0.2 payloads."""
        from simba_mcp.server import create_model

        ctx, client = self._ctx_capturing()
        await create_model(**self.BASE_ARGS, ctx=ctx)
        (payload,) = client.create_model.call_args.args
        assert payload["config"] == {
            "trend": False,
            "seasonality": False,
            "likelihood": "normal",
        }

    @pytest.mark.anyio
    async def test_architecture_params_passthrough(self):
        from simba_mcp.server import create_model

        ctx, client = self._ctx_capturing()
        await create_model(
            **self.BASE_ARGS,
            saturation_type="generalized_log",
            transform_order="saturation_first",
            link="log",
            ctx=ctx,
        )
        (payload,) = client.create_model.call_args.args
        assert payload["config"]["saturation_type"] == "generalized_log"
        assert payload["config"]["transform_order"] == "saturation_first"
        assert payload["config"]["link"] == "log"

    @pytest.mark.anyio
    async def test_channel_groups_passthrough(self):
        from simba_mcp.server import create_model

        groups = [{"name": "Long", "channels": ["TV", "OOH"]}]
        ctx, client = self._ctx_capturing()
        await create_model(**self.BASE_ARGS, channel_groups=groups, ctx=ctx)
        (payload,) = client.create_model.call_args.args
        assert payload["config"]["channel_groups"] == groups

    @pytest.mark.anyio
    async def test_empty_channel_groups_omitted(self):
        from simba_mcp.server import create_model

        ctx, client = self._ctx_capturing()
        await create_model(**self.BASE_ARGS, channel_groups=[], ctx=ctx)
        (payload,) = client.create_model.call_args.args
        assert "channel_groups" not in payload["config"]

    @pytest.mark.anyio
    async def test_control_reference_passthrough(self):
        """#452: control attribution reference points forward verbatim into
        config.control_reference (same pattern as channel_groups)."""
        from simba_mcp.server import create_model

        reference = {"_default": "auto", "relative_price": "average"}
        ctx, client = self._ctx_capturing()
        await create_model(
            **self.BASE_ARGS, link="log", control_reference=reference, ctx=ctx
        )
        (payload,) = client.create_model.call_args.args
        assert payload["config"]["control_reference"] == reference

    @pytest.mark.anyio
    async def test_empty_control_reference_omitted(self):
        """Omitted/empty keeps legacy all-'absent' semantics — the key must
        not appear in the payload at all."""
        from simba_mcp.server import create_model

        ctx, client = self._ctx_capturing()
        await create_model(**self.BASE_ARGS, control_reference=None, ctx=ctx)
        (payload,) = client.create_model.call_args.args
        assert "control_reference" not in payload["config"]

    def test_docstring_no_invalid_likelihood(self):
        """The API rejects 'negbinomial'; the docstring must name the canonical
        values instead (negativebinomial et al.)."""
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "create_model")
        assert "negbinomial" not in tool.description.replace("negativebinomial", "")
        assert "negativebinomial" in tool.description
        assert "lognormal" in tool.description

    def test_docstring_documents_new_prior_fields(self):
        """Half-life, theta, dual-weight, and sat-shape prior overrides must be
        discoverable from the docstring."""
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "create_model")
        for field in (
            "half_life_lower",
            "half_life_upper",
            "theta_mean",
            "theta_sd",
            "dual_weight_mean",
            "dual_weight_sd",
            "sat_shape_mean",
            "sat_shape_sd",
        ):
            assert field in tool.description, f"{field} missing from docstring"


class TestUploadData:
    """upload_data csv_path support and validation (issue #14)."""

    def _ctx_capturing(self):
        from unittest.mock import AsyncMock, MagicMock

        client = MagicMock()
        client.upload_csv = AsyncMock(return_value={"id": 1})
        ctx = MagicMock()
        ctx.request_context.lifespan_context.client = client
        return ctx, client

    @pytest.fixture(autouse=True)
    def _local_files_on(self, monkeypatch):
        monkeypatch.setenv("SIMBA_MCP_ALLOW_LOCAL_FILES", "1")

    @pytest.mark.anyio
    async def test_csv_path_reads_file_and_defaults_name(self, tmp_path):
        from simba_mcp.server import upload_data

        f = tmp_path / "mydata.csv"
        f.write_text("date,kpi\n2024-01-01,1\n", encoding="utf-8")
        ctx, client = self._ctx_capturing()
        await upload_data(csv_path=str(f), ctx=ctx)
        content, name = client.upload_csv.call_args.args
        assert content.startswith("date,kpi")
        assert name == "mydata"

    @pytest.mark.anyio
    async def test_both_args_rejected_without_api_call(self):
        from simba_mcp.server import upload_data

        ctx, client = self._ctx_capturing()
        res = await upload_data(csv_content="a,b\n", csv_path="x.csv", ctx=ctx)
        assert res["_status_code"] == 400
        client.upload_csv.assert_not_called()

    @pytest.mark.anyio
    async def test_neither_arg_rejected(self):
        from simba_mcp.server import upload_data

        ctx, client = self._ctx_capturing()
        res = await upload_data(ctx=ctx)
        assert res["_status_code"] == 400
        client.upload_csv.assert_not_called()

    @pytest.mark.anyio
    async def test_missing_file_rejected(self, tmp_path):
        from simba_mcp.server import upload_data

        ctx, client = self._ctx_capturing()
        res = await upload_data(csv_path=str(tmp_path / "nope.csv"), ctx=ctx)
        assert res["_status_code"] == 400
        assert "not found" in res["error"].lower()
        client.upload_csv.assert_not_called()

    @pytest.mark.anyio
    async def test_oversized_file_rejected_preflight(self, tmp_path, monkeypatch):
        import simba_mcp.server as server_mod

        monkeypatch.setattr(server_mod, "MAX_UPLOAD_BYTES", 10)
        f = tmp_path / "big.csv"
        f.write_text("x" * 100, encoding="utf-8")
        ctx, client = self._ctx_capturing()
        res = await server_mod.upload_data(csv_path=str(f), ctx=ctx)
        assert res["_status_code"] == 413
        client.upload_csv.assert_not_called()

    @pytest.mark.anyio
    async def test_csv_path_disabled_on_http_transport(self, tmp_path, monkeypatch):
        import simba_mcp.server as server_mod

        monkeypatch.delenv("SIMBA_MCP_ALLOW_LOCAL_FILES", raising=False)
        monkeypatch.setattr(server_mod, "_serving_http", True)
        f = tmp_path / "d.csv"
        f.write_text("a,b\n", encoding="utf-8")
        ctx, client = self._ctx_capturing()
        res = await server_mod.upload_data(csv_path=str(f), ctx=ctx)
        assert res["_status_code"] == 403
        assert "HTTP/SSE" in res["error"]
        client.upload_csv.assert_not_called()

    @pytest.mark.anyio
    async def test_csv_path_disabled_by_env_on_stdio(self, tmp_path, monkeypatch):
        """Explicit SIMBA_MCP_ALLOW_LOCAL_FILES=0 must not blame HTTP/SSE."""
        import simba_mcp.server as server_mod

        monkeypatch.setenv("SIMBA_MCP_ALLOW_LOCAL_FILES", "0")
        monkeypatch.setattr(server_mod, "_serving_http", False)
        f = tmp_path / "d.csv"
        f.write_text("a,b\n", encoding="utf-8")
        ctx, client = self._ctx_capturing()
        res = await server_mod.upload_data(csv_path=str(f), ctx=ctx)
        assert res["_status_code"] == 403
        assert "SIMBA_MCP_ALLOW_LOCAL_FILES" in res["error"]
        assert "HTTP/SSE" not in res["error"]
        client.upload_csv.assert_not_called()

    @pytest.mark.anyio
    async def test_env_override_reenables_on_http(self, tmp_path, monkeypatch):
        import simba_mcp.server as server_mod

        monkeypatch.setenv("SIMBA_MCP_ALLOW_LOCAL_FILES", "1")
        monkeypatch.setattr(server_mod, "_serving_http", True)
        f = tmp_path / "d.csv"
        f.write_text("a,b\n", encoding="utf-8")
        ctx, client = self._ctx_capturing()
        await server_mod.upload_data(csv_path=str(f), ctx=ctx)
        client.upload_csv.assert_called_once()

    @pytest.mark.anyio
    async def test_csv_content_path_unchanged(self):
        """Backward compat: csv_content behaves exactly as before."""
        from simba_mcp.server import upload_data

        ctx, client = self._ctx_capturing()
        await upload_data(csv_content="a,b\n1,2\n", name="x", ctx=ctx)
        assert client.upload_csv.call_args.args == ("a,b\n1,2\n", "x")

    def test_docstring_no_stale_limits(self):
        """Docstring must not claim 50 MB or a hardcoded 52-row minimum."""
        tool = next(t for t in mcp._tool_manager.list_tools() if t.name == "upload_data")
        assert "50 MB" not in tool.description
        assert "Minimum 52 rows" not in tool.description
        assert "min_rows" in tool.description


class TestGetModelResultsFiltering:
    """Channel filtering, grid downsampling, and csv format (issue #13)."""

    @staticmethod
    def _payload():
        curve_row = lambda i: {
            "Spend": float(i),
            "tv_activity": i * 1.0,
            "tv_activity_lower": i * 0.8,
            "tv_activity_upper_50": i * 1.1,
            "search_activity": i * 2.0,
            "search_activity_lower": i * 1.6,
        }
        return {
            "model_hash": "abc",
            "sections_available": ["response_curves"],
            "results": {
                "response_curves": [curve_row(i) for i in range(100)],
                "marginal_curves": [curve_row(i) for i in range(100)],
                "decay_curves": {"tv_activity": {"mean": 0.5}, "search_activity": {"mean": 0.4}},
                "saturation": {
                    "saturation_type": "tanh",
                    "channels": {"tv_activity": {}, "search_activity": {}},
                },
                "channel_summary": [
                    {"Channel": "tv_activity", "ROI": 2.0},
                    {"Channel": "search_activity", "ROI": 5.0},
                ],
                "coefficients": [{"Channel": "tv_activity"}, {"Channel": "search_activity"}],
                "mroi_summary": {
                    "channels": [{"channel": "tv_activity"}, {"channel": "search_activity"}]
                },
                "contributions": [
                    {"Date": 1, "tv_activity": 1.0, "category_trend": 2.0, "Base": 3.0}
                ],
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
        assert set(r["response_curves"][0]) == {"Spend", "search_activity", "search_activity_lower"}
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
            "Date",
            "tv_activity",
            "category_trend",
            "Base",
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
