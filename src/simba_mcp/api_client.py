"""
Async HTTP client for the Simba API v1.

Wraps all API v1 endpoints so MCP tools stay thin and declarative.
"""

from typing import Any

import httpx

DEFAULT_TIMEOUT = 60.0


class SimbaAPIClient:
    """Thin async wrapper around Simba's API v1 endpoints."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
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
            return error_body
        return response.json()

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        client = await self._get_client()
        response = await client.request(method, path, **kwargs)
        return await self._parse_response(response)

    # -- Ingest --

    async def get_schema(self) -> dict:
        return await self._request("GET", "/api/v1/ingest/schema")

    async def upload_csv(self, csv_content: str, name: str = "") -> dict:
        """Upload CSV text content. For MCP, CSV arrives as a string."""
        client = await self._get_client()
        params = {"name": name} if name else {}
        response = await client.post(
            "/api/v1/ingest",
            content=csv_content.encode("utf-8"),
            headers={"Content-Type": "text/csv"},
            params=params,
        )
        return await self._parse_response(response)

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
