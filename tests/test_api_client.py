"""Unit tests for the MCP API client — verifies correct HTTP calls without a real server."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from simba_mcp.api_client import SimbaAPIClient


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
    async def test_raises_after_max_transport_errors(self):
        """Persistent transport errors are raised after exhausting retries."""

        class DeadTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                await request.aread()
                raise httpx.ConnectError("connection refused")

        client = self._make_client(DeadTransport())
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.ConnectError):
                await client.get_schema()

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
