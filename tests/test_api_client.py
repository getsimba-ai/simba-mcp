"""Unit tests for the MCP API client — verifies correct HTTP calls without a real server."""

import pytest
import httpx

from simba_mcp.api_client import SimbaAPIClient


@pytest.fixture
def mock_transport():
    """Create a mock httpx transport that records requests."""
    requests = []

    class MockTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            body = await request.aread()
            requests.append({
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": body,
            })
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
        assert "bearer simba_sk_testkey123" in requests[0]["headers"].get("authorization", "").lower()

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
                body = await request.aread()
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
