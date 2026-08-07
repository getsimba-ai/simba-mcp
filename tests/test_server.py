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
        tool = next(t for t in mcp._tool_manager.list_tools()
                    if t.name == "upload_data")
        assert "50 MB" not in tool.description
        assert "Minimum 52 rows" not in tool.description
        assert "min_rows" in tool.description
