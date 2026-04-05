"""
Async HTTP client for the Simba API v1.

Wraps all API v1 endpoints so MCP tools stay thin and declarative.
"""

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60.0
MAX_RETRIES = 3
BACKOFF_BASE = 0.5
RETRIABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

AUTH_HELP = (
    "This MCP server requires a Simba account. "
    "If you're already a customer, create an API key at Profile > API Keys in the Simba UI. "
    "Not a customer yet? Book a call to get started: "
    "https://calendly.com/niall-oulton"
)


class SimbaAPIClient:
    """Thin async wrapper around Simba's API v1 endpoints."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=DEFAULT_TIMEOUT,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _parse_response(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            try:
                error_body = response.json()
            except Exception:
                error_body = {"error": response.text or response.reason_phrase}
            error_body["_status_code"] = response.status_code
            if response.status_code in (401, 403):
                error_body["_help"] = AUTH_HELP
            return error_body
        return response.json()

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        if not self._api_key:
            return {
                "error": "SIMBA_API_KEY is not set. " + AUTH_HELP,
                "_status_code": 401,
                "_help": AUTH_HELP,
            }
        client = await self._get_client()
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.request(method, path, **kwargs)
                if response.status_code in RETRIABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                    delay = BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        "Retryable %d from %s %s (attempt %d/%d, retrying in %.1fs)",
                        response.status_code,
                        method,
                        path,
                        attempt + 1,
                        MAX_RETRIES,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                return await self._parse_response(response)
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    delay = BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        "Transport error on %s %s (attempt %d/%d, retrying in %.1fs): %s",
                        method,
                        path,
                        attempt + 1,
                        MAX_RETRIES,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]

    # -- Ingest --

    async def get_schema(self) -> dict:
        return await self._request("GET", "/api/v1/ingest/schema")

    async def upload_csv(self, csv_content: str, name: str = "") -> dict:
        """Upload CSV text content. For MCP, CSV arrives as a string."""
        params = {"name": name} if name else {}
        return await self._request(
            "POST",
            "/api/v1/ingest",
            content=csv_content.encode("utf-8"),
            headers={"Content-Type": "text/csv"},
            params=params,
        )

    # -- Models --

    async def list_models(
        self,
        include_unsaved: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        return await self._request(
            "GET",
            "/api/v1/models",
            params={
                "include_unsaved": str(include_unsaved).lower(),
                "limit": limit,
                "offset": offset,
            },
        )

    async def create_model(self, payload: dict) -> dict:
        return await self._request("POST", "/api/v1/models", json=payload)

    async def get_model_status(self, model_hash: str) -> dict:
        return await self._request("GET", f"/api/v1/models/{model_hash}/status")

    async def get_model_results(
        self,
        model_hash: str,
        sections: str = "",
        fmt: str = "json",
    ) -> dict:
        params: dict[str, str] = {"format": fmt}
        if sections:
            params["sections"] = sections
        return await self._request(
            "GET",
            f"/api/v1/models/{model_hash}/results",
            params=params,
        )

    # -- Optimizer --

    async def run_optimizer(self, model_hash: str, payload: dict) -> dict:
        return await self._request(
            "POST",
            f"/api/v1/models/{model_hash}/optimize",
            json=payload,
        )

    async def get_optimizer_results(self, model_hash: str) -> dict:
        return await self._request("GET", f"/api/v1/models/{model_hash}/optimize")

    # -- Scenario Planner --

    async def get_scenario_template(self, model_hash: str, periods_forward: int = 12) -> dict:
        return await self._request(
            "POST",
            f"/api/v1/models/{model_hash}/scenario/template",
            json={"periods_forward": periods_forward},
        )

    async def run_scenario(self, model_hash: str, payload: dict) -> dict:
        return await self._request(
            "POST",
            f"/api/v1/models/{model_hash}/scenario",
            json=payload,
        )

    async def get_scenario_results(self, model_hash: str) -> dict:
        return await self._request("GET", f"/api/v1/models/{model_hash}/scenario")
