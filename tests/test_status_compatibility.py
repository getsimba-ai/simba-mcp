"""Status response compatibility across backend versions."""

from unittest.mock import patch

import httpx
import pytest

from simba_mcp.api_client import SimbaAPIClient
from simba_mcp.server import get_model_status


@pytest.mark.anyio
@pytest.mark.parametrize(
    "liveness",
    [
        None,
        {"available": False, "reason": "heartbeat_unavailable"},
        {"available": False, "reason": "not_fitting"},
        {
            "available": True,
            "last_heartbeat_at": 1700000000.0,
            "heartbeat_age_seconds": 901.0,
            "stall_timeout_seconds": 900,
            "seconds_until_stall_threshold": 0.0,
            "stall_threshold_exceeded": True,
        },
    ],
)
async def test_status_payload_survives_http_client_and_tool(liveness):
    payload = {"status": "under way", "progress": 25, "future_field": {"value": 1}}
    if liveness is not None:
        payload["fit_liveness"] = liveness
    if liveness == {"available": False, "reason": "not_fitting"}:
        payload["status"] = "complete"

    def respond(request):
        assert request.method == "GET"
        assert request.url.path == "/api/v1/models/example/status"
        return httpx.Response(200, json=payload)

    client = SimbaAPIClient("https://example.test", "test-key")
    async with httpx.AsyncClient(
        base_url="https://example.test", transport=httpx.MockTransport(respond)
    ) as transport_client:
        client._client = transport_client
        with patch("simba_mcp.tools.models._client", return_value=client):
            result = await get_model_status("example")
    assert result == payload
