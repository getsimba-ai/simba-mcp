"""Unit tests for the MCP API client — verifies correct HTTP calls without a real server."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from simba_mcp.api_client import AUTH_HELP, SimbaAPIClient


@pytest.fixture
def mock_transport():
    """Create a mock httpx transport that records requests."""
    requests = []

    class MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            body = await request.aread()
            requests.append(
                {
                    "method": request.method,
                    "url": str(request.url),
                    "headers": dict(request.headers),
                    "body": body,
                }
            )
            return httpx.Response(200, json={"ok": True})

    return MockTransport(), requests


@pytest.fixture
def client_with_mock(mock_transport):
    """SimbaAPIClient backed by mock transport."""
    transport, requests = mock_transport
    api_client = SimbaAPIClient("http://test-simba:5005", "simba_sk_testkey123")
    api_client._client = httpx.AsyncClient(
        base_url="http://test-simba:5005",
        headers={"Authorization": "Bearer simba_sk_testkey123"},
        transport=transport,
    )
    return api_client, requests


class TestAPIClientAuth:
    @pytest.mark.anyio
    async def test_bearer_token_sent(self, client_with_mock):
        """Every request includes the Bearer token."""
        client, requests = client_with_mock
        await client.get_schema()
        assert len(requests) == 1
        assert (
            "bearer simba_sk_testkey123" in requests[0]["headers"].get("authorization", "").lower()
        )

    @pytest.mark.anyio
    async def test_base_url_used(self, client_with_mock):
        """Requests go to the configured base URL."""
        client, requests = client_with_mock
        await client.list_models()
        assert "test-simba:5005" in requests[0]["url"]


class TestAPIClientEndpoints:
    @pytest.mark.anyio
    async def test_get_schema_path(self, client_with_mock):
        client, requests = client_with_mock
        await client.get_schema()
        assert "/api/v1/ingest/schema" in requests[0]["url"]

    @pytest.mark.anyio
    async def test_upload_csv_path_and_content_type(self, client_with_mock):
        client, requests = client_with_mock
        await client.upload_csv("date,value\n2024-01-01,100", name="test")
        assert "/api/v1/ingest" in requests[0]["url"]
        assert requests[0]["method"] == "POST"
        assert "text/csv" in requests[0]["headers"].get("content-type", "")

    @pytest.mark.anyio
    async def test_list_models_path(self, client_with_mock):
        client, requests = client_with_mock
        await client.list_models(include_unsaved=True, limit=10)
        assert "/api/v1/models" in requests[0]["url"]
        assert "include_unsaved=true" in requests[0]["url"]

    @pytest.mark.anyio
    async def test_create_model_path(self, client_with_mock):
        client, requests = client_with_mock
        await client.create_model({"data_source": {"uploaded_file_id": 1}})
        assert "/api/v1/models" in requests[0]["url"]
        assert requests[0]["method"] == "POST"

    @pytest.mark.anyio
    async def test_get_model_status_path(self, client_with_mock):
        client, requests = client_with_mock
        await client.get_model_status("abc123")
        assert "/api/v1/models/abc123/status" in requests[0]["url"]

    @pytest.mark.anyio
    async def test_get_model_results_path(self, client_with_mock):
        client, requests = client_with_mock
        await client.get_model_results("abc123", sections="channel_summary")
        assert "/api/v1/models/abc123/results" in requests[0]["url"]
        assert "sections=channel_summary" in requests[0]["url"]

    @pytest.mark.anyio
    async def test_run_optimizer_path(self, client_with_mock):
        client, requests = client_with_mock
        await client.run_optimizer("abc123", {"total_budget": 100000})
        assert "/api/v1/models/abc123/optimize" in requests[0]["url"]
        assert requests[0]["method"] == "POST"

    @pytest.mark.anyio
    async def test_get_optimizer_results_path(self, client_with_mock):
        client, requests = client_with_mock
        await client.get_optimizer_results("abc123")
        assert "/api/v1/models/abc123/optimize" in requests[0]["url"]
        assert requests[0]["method"] == "GET"

    @pytest.mark.anyio
    async def test_get_scenario_template_path(self, client_with_mock):
        client, requests = client_with_mock
        await client.get_scenario_template("abc123", periods_forward=8)
        assert "/api/v1/models/abc123/scenario/template" in requests[0]["url"]
        assert requests[0]["method"] == "POST"

    @pytest.mark.anyio
    async def test_run_scenario_path(self, client_with_mock):
        client, requests = client_with_mock
        await client.run_scenario("abc123", {"scenario_data": [{"Date": "2025-01-06"}]})
        assert "/api/v1/models/abc123/scenario" in requests[0]["url"]
        assert requests[0]["method"] == "POST"

    @pytest.mark.anyio
    async def test_get_scenario_results_path(self, client_with_mock):
        client, requests = client_with_mock
        await client.get_scenario_results("abc123")
        assert "/api/v1/models/abc123/scenario" in requests[0]["url"]
        assert requests[0]["method"] == "GET"

    @pytest.mark.anyio
    async def test_rename_model_path(self, client_with_mock):
        """#575: PATCH /models/{hash} with the name body."""
        import json as _json

        client, requests = client_with_mock
        await client.rename_model("abc123", "Q3 base")
        assert "/api/v1/models/abc123" in requests[0]["url"]
        assert requests[0]["method"] == "PATCH"
        assert _json.loads(requests[0]["body"]) == {"name": "Q3 base"}

    @pytest.mark.anyio
    async def test_save_model_path(self, client_with_mock):
        """#575: POST /models/{hash}/save; project_id omitted when None."""
        import json as _json

        client, requests = client_with_mock
        await client.save_model("abc123", "Q3 base")
        assert "/api/v1/models/abc123/save" in requests[0]["url"]
        assert requests[0]["method"] == "POST"
        assert _json.loads(requests[0]["body"]) == {"name": "Q3 base"}

        await client.save_model("abc123", "Q3 base", project_id=12)
        assert _json.loads(requests[1]["body"]) == {"name": "Q3 base", "project_id": 12}

    @pytest.mark.anyio
    async def test_update_run_paths_per_artifact(self, client_with_mock):
        """#576: artifact selects the URL segment (optimize vs scenario)."""
        import json as _json

        client, requests = client_with_mock
        await client.update_run("optimizer", "abc123", "opt_9", name="Reference plan")
        assert "/api/v1/models/abc123/optimize/runs/opt_9" in requests[0]["url"]
        assert requests[0]["method"] == "PATCH"
        assert _json.loads(requests[0]["body"]) == {"name": "Reference plan"}

        await client.update_run("scenario", "abc123", "scn_9", tags=["ladder"])
        assert "/api/v1/models/abc123/scenario/runs/scn_9" in requests[1]["url"]
        assert _json.loads(requests[1]["body"]) == {"tags": ["ladder"]}

    @pytest.mark.anyio
    async def test_unknown_artifact_returns_structured_error(self, client_with_mock):
        """Never a raise: SDK v2 masks raised exceptions to an info-free
        'Error executing tool ...' at the client — the guidance must travel
        in the tool result. Covers all three artifact-taking methods."""
        client, requests = client_with_mock
        for coro in (
            client.update_run("portfolio", "abc123", "opt_9", name="x"),
            client.set_run_pinned("portfolio", "abc123", "opt_9", True),
            client.list_runs("portfolio", "abc123"),
        ):
            result = await coro
            assert result["_status_code"] == 400
            assert "Unknown artifact 'portfolio'" in result["error"]
            assert "optimizer, scenario" in result["error"]
        assert requests == []

    @pytest.mark.anyio
    async def test_set_run_pinned_body(self, client_with_mock):
        """#576: pinned bool sent as body; None sends no body (toggle)."""
        import json as _json

        client, requests = client_with_mock
        await client.set_run_pinned("optimizer", "abc123", "opt_9", True)
        assert "/api/v1/models/abc123/optimize/runs/opt_9/pin" in requests[0]["url"]
        assert requests[0]["method"] == "POST"
        assert _json.loads(requests[0]["body"]) == {"pinned": True}

        await client.set_run_pinned("optimizer", "abc123", "opt_9")
        assert requests[1]["body"] == b""

    @pytest.mark.anyio
    async def test_get_model_and_delete_model_paths(self, client_with_mock):
        """#45: GET/DELETE /api/v1/models/{hash}."""
        client, requests = client_with_mock
        await client.get_model("abc123")
        assert requests[0]["url"].endswith("/api/v1/models/abc123")
        assert requests[0]["method"] == "GET"

        await client.delete_model("abc123")
        assert requests[1]["url"].endswith("/api/v1/models/abc123")
        assert requests[1]["method"] == "DELETE"

    @pytest.mark.anyio
    async def test_list_runs_paths_per_artifact(self, client_with_mock):
        """#21: artifact selects the segment; limit/offset ride the query."""
        client, requests = client_with_mock
        await client.list_runs("optimizer", "abc123", limit=10, offset=20)
        assert "/api/v1/models/abc123/optimize/runs" in requests[0]["url"]
        assert requests[0]["method"] == "GET"
        assert "limit=10" in requests[0]["url"] and "offset=20" in requests[0]["url"]

        await client.list_runs("scenario", "abc123")
        assert "/api/v1/models/abc123/scenario/runs" in requests[1]["url"]

    @pytest.mark.anyio
    async def test_get_scenario_results_run_id_path(self, client_with_mock):
        """#21: run_id switches to the by-run route; without it, model-level."""
        client, requests = client_with_mock
        await client.get_scenario_results("abc123", run_id="scn_9")
        assert "/api/v1/models/abc123/scenario/runs/scn_9" in requests[0]["url"]
        assert requests[0]["method"] == "GET"

        await client.get_scenario_results("abc123")
        assert requests[1]["url"].endswith("/api/v1/models/abc123/scenario")

    @pytest.mark.anyio
    async def test_list_uploads_params(self, client_with_mock):
        """#21: GET /api/v1/ingest; name only sent when non-empty."""
        client, requests = client_with_mock
        await client.list_uploads(limit=5, offset=10, name="q3")
        assert "/api/v1/ingest" in requests[0]["url"]
        assert requests[0]["method"] == "GET"
        assert "limit=5" in requests[0]["url"] and "offset=10" in requests[0]["url"]
        assert "name=q3" in requests[0]["url"]

        await client.list_uploads()
        assert "name=" not in requests[1]["url"]

    @pytest.mark.anyio
    async def test_get_upload_path(self, client_with_mock):
        """#21: GET /api/v1/ingest/{id}."""
        client, requests = client_with_mock
        await client.get_upload(17)
        assert requests[0]["url"].endswith("/api/v1/ingest/17")
        assert requests[0]["method"] == "GET"


class TestAPIClientErrorHandling:
    @pytest.fixture
    def error_transport(self):
        """Transport that returns a 403 with a JSON error body."""
        requests = []

        class ErrorTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                await request.aread()
                requests.append({"method": request.method, "url": str(request.url)})
                return httpx.Response(
                    403,
                    json={"error": "API key missing required scope: create:models"},
                )

        return ErrorTransport(), requests

    @pytest.fixture
    def client_with_error(self, error_transport):
        transport, requests = error_transport
        api_client = SimbaAPIClient("http://test-simba:5005", "simba_sk_testkey123")
        api_client._client = httpx.AsyncClient(
            base_url="http://test-simba:5005",
            headers={"Authorization": "Bearer simba_sk_testkey123"},
            transport=transport,
        )
        return api_client, requests

    @pytest.mark.anyio
    async def test_error_returns_api_body(self, client_with_error):
        """HTTP errors return the API's JSON error body instead of raising."""
        client, _ = client_with_error
        result = await client.create_model({"data_source": {"uploaded_file_id": 1}})
        assert result["error"] == "API key missing required scope: create:models"
        assert result["_status_code"] == 403

    @pytest.mark.anyio
    async def test_403_includes_help(self, client_with_error):
        """A 403 response includes a _help field with customer guidance."""
        client, _ = client_with_error
        result = await client.create_model({"data_source": {"uploaded_file_id": 1}})
        assert result["_help"] == AUTH_HELP
        assert "calendly.com" in result["_help"]

    @pytest.mark.anyio
    async def test_401_includes_help(self):
        """A 401 response includes a _help field with customer guidance."""

        class UnauthorizedTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                await request.aread()
                return httpx.Response(401, json={"error": "Invalid API key"})

        api_client = SimbaAPIClient("http://test-simba:5005", "simba_sk_badkey")
        api_client._client = httpx.AsyncClient(
            base_url="http://test-simba:5005",
            headers={"Authorization": "Bearer simba_sk_badkey"},
            transport=UnauthorizedTransport(),
        )
        result = await api_client.get_schema()
        assert result["_status_code"] == 401
        assert result["_help"] == AUTH_HELP

    @pytest.mark.anyio
    async def test_missing_api_key_returns_error_without_network_call(self):
        """When no API key is configured, requests fail immediately with guidance."""
        api_client = SimbaAPIClient("http://test-simba:5005", "")
        result = await api_client.get_schema()
        assert result["_status_code"] == 401
        assert "SIMBA_API_KEY is not set" in result["error"]
        assert result["_help"] == AUTH_HELP
        assert "calendly.com" in result["_help"]


class TestAPIClientRetry:
    """Tests for retry logic with exponential backoff."""

    @staticmethod
    def _make_client(transport):
        api_client = SimbaAPIClient("http://test-simba:5005", "simba_sk_testkey123")
        api_client._client = httpx.AsyncClient(
            base_url="http://test-simba:5005",
            headers={"Authorization": "Bearer simba_sk_testkey123"},
            transport=transport,
        )
        return api_client

    @pytest.mark.anyio
    async def test_retries_on_server_error_then_succeeds(self):
        """A 502 on attempt 1 is retried and succeeds on attempt 2."""
        call_count = 0

        class RetryTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                nonlocal call_count
                call_count += 1
                await request.aread()
                if call_count == 1:
                    return httpx.Response(502, json={"error": "bad gateway"})
                return httpx.Response(200, json={"ok": True})

        client = self._make_client(RetryTransport())
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.get_schema()
        assert result == {"ok": True}
        assert call_count == 2

    @pytest.mark.anyio
    async def test_retries_on_429_then_succeeds(self):
        """A 429 rate-limit response is retried."""
        call_count = 0

        class RateLimitTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                nonlocal call_count
                call_count += 1
                await request.aread()
                if call_count <= 2:
                    return httpx.Response(429, json={"error": "rate limited"})
                return httpx.Response(200, json={"ok": True})

        client = self._make_client(RateLimitTransport())
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.get_schema()
        assert result == {"ok": True}
        assert call_count == 3

    @pytest.mark.anyio
    async def test_gives_up_after_max_retries(self):
        """After MAX_RETRIES attempts of 500, the error response is returned."""

        class AlwaysFailTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                await request.aread()
                return httpx.Response(500, json={"error": "server error"})

        client = self._make_client(AlwaysFailTransport())
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.get_schema()
        assert result["_status_code"] == 500

    @pytest.mark.anyio
    async def test_retries_on_transport_error_then_succeeds(self):
        """A transient network error is retried and succeeds on attempt 2."""
        call_count = 0

        class FlakeyTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                nonlocal call_count
                call_count += 1
                await request.aread()
                if call_count == 1:
                    raise httpx.ConnectError("connection refused")
                return httpx.Response(200, json={"ok": True})

        client = self._make_client(FlakeyTransport())
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.get_schema()
        assert result == {"ok": True}
        assert call_count == 2

    @pytest.mark.anyio
    async def test_structured_error_after_max_transport_errors(self):
        """Persistent transport errors return a structured payload, never raise:
        SDK v2 masks raised exceptions to an info-free "Error executing tool"
        at the client, so the cause must travel in the tool result instead."""

        class DeadTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                await request.aread()
                raise httpx.ConnectError("connection refused")

        client = self._make_client(DeadTransport())
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.get_schema()
        assert result["_status_code"] == 503
        assert "unreachable" in result["error"]
        assert "connection refused" in result["error"]

    @pytest.mark.anyio
    async def test_non_retriable_status_not_retried(self):
        """A 403 is not retried — it's returned immediately."""
        call_count = 0

        class ForbiddenTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                nonlocal call_count
                call_count += 1
                await request.aread()
                return httpx.Response(403, json={"error": "forbidden"})

        client = self._make_client(ForbiddenTransport())
        result = await client.get_schema()
        assert result["_status_code"] == 403
        assert call_count == 1


class TestCsvResponses:
    """Non-JSON success bodies are returned as {'format': 'csv', ...} (issue #13)."""

    @staticmethod
    def _make_client(transport):
        api_client = SimbaAPIClient("http://test-simba:5005", "simba_sk_testkey123")
        api_client._client = httpx.AsyncClient(
            base_url="http://test-simba:5005",
            headers={"Authorization": "Bearer simba_sk_testkey123"},
            transport=transport,
        )
        return api_client

    @pytest.mark.anyio
    async def test_csv_body_wrapped_not_json_decoded(self):
        class CsvTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                await request.aread()
                return httpx.Response(
                    200,
                    text="# channel_summary\nChannel,ROI\ntv_activity,2.0\n",
                    headers={"content-type": "text/csv"},
                )

        client = self._make_client(CsvTransport())
        result = await client.get_model_results("abc", fmt="csv")
        assert result["format"] == "csv"
        assert result["content"].startswith("# channel_summary")

    @pytest.mark.anyio
    async def test_fmt_param_sent_as_format_query(self):
        seen = {}

        class RecordingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                await request.aread()
                seen["url"] = str(request.url)
                return httpx.Response(200, json={"ok": True})

        client = self._make_client(RecordingTransport())
        await client.get_model_results("abc", fmt="csv")
        assert "format=csv" in seen["url"]


class TestCallerKeyOverride:
    """Bring-your-own-key (#51): the CALLER_API_KEY ContextVar overrides the
    env key per request; "" hard-fails with guidance; None keeps env-key
    behavior; concurrent tasks can never see each other's keys."""

    @pytest.mark.anyio
    async def test_caller_key_overrides_env_key(self, client_with_mock):
        from simba_mcp.api_client import CALLER_API_KEY

        client, requests = client_with_mock
        token = CALLER_API_KEY.set("simba_sk_callerAAA")
        try:
            await client.get_schema()
        finally:
            CALLER_API_KEY.reset(token)
        auth = requests[0]["headers"].get("authorization", "")
        assert auth == "Bearer simba_sk_callerAAA"
        assert "testkey123" not in auth

    @pytest.mark.anyio
    async def test_empty_caller_key_fails_with_guidance_before_any_request(self, client_with_mock):
        from simba_mcp.api_client import CALLER_API_KEY, HTTP_AUTH_HELP

        client, requests = client_with_mock
        token = CALLER_API_KEY.set("")
        try:
            result = await client.get_schema()
        finally:
            CALLER_API_KEY.reset(token)
        assert result["_status_code"] == 401
        assert HTTP_AUTH_HELP in result["error"]
        assert requests == []

    @pytest.mark.anyio
    async def test_no_override_keeps_env_key(self, client_with_mock):
        """None (stdio) = pre-#51 behavior, the env-configured key."""
        client, requests = client_with_mock
        await client.get_schema()
        assert requests[0]["headers"].get("authorization") == "Bearer simba_sk_testkey123"

    @pytest.mark.anyio
    async def test_override_merges_with_existing_request_headers(self, client_with_mock):
        """upload_csv passes Content-Type per-request; the auth override must
        merge with it, not clobber it."""
        from simba_mcp.api_client import CALLER_API_KEY

        client, requests = client_with_mock
        token = CALLER_API_KEY.set("simba_sk_callerBBB")
        try:
            await client.upload_csv("a,b\n1,2", name="d")
        finally:
            CALLER_API_KEY.reset(token)
        headers = requests[0]["headers"]
        assert headers.get("authorization") == "Bearer simba_sk_callerBBB"
        assert headers.get("content-type") == "text/csv"

    @pytest.mark.anyio
    async def test_concurrent_tasks_keep_their_own_keys(self, client_with_mock):
        """Two tasks, two keys, one shared client: each request must carry
        exactly its own task's key — the leak this design must preclude."""
        import anyio

        from simba_mcp.api_client import CALLER_API_KEY

        client, requests = client_with_mock

        async def call_as(key):
            CALLER_API_KEY.set(key)  # task-local: dies with the task
            await client.get_schema()

        async with anyio.create_task_group() as tg:
            tg.start_soon(call_as, "simba_sk_userONE")
            tg.start_soon(call_as, "simba_sk_userTWO")

        seen = sorted(r["headers"]["authorization"] for r in requests)
        assert seen == ["Bearer simba_sk_userONE", "Bearer simba_sk_userTWO"]
