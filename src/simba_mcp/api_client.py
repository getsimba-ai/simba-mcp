"""
Async HTTP client for the Simba API v1.

Wraps all API v1 endpoints so MCP tools stay thin and declarative.
"""

import asyncio
import contextvars
import logging
from typing import Any, ClassVar

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

HTTP_AUTH_HELP = (
    "On hosted (HTTP) deployments every caller authenticates with their OWN "
    "Simba API key: send it as the HTTP Authorization header "
    '("Authorization: Bearer simba_sk_..."). Create a key at '
    "Profile > API Keys in the Simba UI. " + AUTH_HELP
)

# Per-caller credential override (bring-your-own-key, issue #51). The server
# layer sets this from the incoming request's Authorization header before
# using the shared client. None = no override (stdio: the env key applies);
# "" = an HTTP caller sent no usable token (every call must fail with
# guidance, never fall back to a shared key). A ContextVar is task-local, so
# concurrent callers can never observe each other's keys by construction.
CALLER_API_KEY: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "simba_caller_api_key", default=None
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
            except ValueError:
                # Non-JSON error body (HTML gateway pages, plain text)
                error_body = {"error": response.text or response.reason_phrase}
            error_body["_status_code"] = response.status_code
            if response.status_code in (401, 403):
                error_body["_help"] = AUTH_HELP
            return error_body
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type.lower():
            # e.g. GET .../results?format=csv returns text/csv
            return {"format": "csv", "content": response.text}
        return response.json()

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        caller_key = CALLER_API_KEY.get()
        if caller_key is None:
            # stdio / no override: the env-configured key is the user's own.
            if not self._api_key:
                return {
                    "error": "SIMBA_API_KEY is not set. " + AUTH_HELP,
                    "_status_code": 401,
                    "_help": AUTH_HELP,
                }
        elif not caller_key:
            return {
                "error": "No API key on this request. " + HTTP_AUTH_HELP,
                "_status_code": 401,
                "_help": HTTP_AUTH_HELP,
            }
        else:
            # Per-request header beats the client-default Authorization in
            # httpx, so the shared connection pool is safe to reuse.
            kwargs["headers"] = {
                **kwargs.get("headers", {}),
                "Authorization": f"Bearer {caller_key}",
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
        # Return a structured payload like every other failure mode instead of
        # raising: SDK v2 masks unexpected exceptions to an info-free
        # "Error executing tool ..." at the client, which would hide the most
        # plausible production failure (backend unreachable during a deploy).
        return {
            "error": (
                f"Simba API unreachable after {MAX_RETRIES} attempts "
                f"({type(last_exc).__name__}: {last_exc}). The backend may be "
                "restarting or the SIMBA_API_URL may be wrong — retry shortly."
            ),
            "_status_code": 503,
        }

    # -- Ingest --

    async def get_schema(self) -> dict:
        return await self._request("GET", "/api/v1/ingest/schema")

    async def upload_csv(self, csv_content: str, name: str = "", filename: str = "") -> dict:
        """Upload CSV text content. For MCP, CSV arrives as a string."""
        params = {}
        if name:
            params["name"] = name
        if filename:
            params["filename"] = filename
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

    async def link_var_model(self, model_hash: str, var_model_hash: str) -> dict:
        return await self._request(
            "POST",
            f"/api/v1/models/{model_hash}/link_var",
            json={"var_model_hash": var_model_hash},
        )

    async def unlink_var_model(self, model_hash: str) -> dict:
        return await self._request("DELETE", f"/api/v1/models/{model_hash}/link_var")

    async def get_contribution_groups(self, model_hash: str) -> dict:
        return await self._request("GET", f"/api/v1/models/{model_hash}/contribution-groups")

    async def put_contribution_groups(self, model_hash: str, groups: list) -> dict:
        return await self._request(
            "PUT",
            f"/api/v1/models/{model_hash}/contribution-groups",
            json={"contribution_groups": groups},
        )

    async def rename_model(self, model_hash: str, name: str) -> dict:
        """Rename a model (#575). Does not save it."""
        return await self._request("PATCH", f"/api/v1/models/{model_hash}", json={"name": name})

    async def save_model(self, model_hash: str, name: str, project_id: int | None = None) -> dict:
        """Save a model into a project under a display name (#575)."""
        payload: dict = {"name": name}
        if project_id is not None:
            payload["project_id"] = project_id
        return await self._request("POST", f"/api/v1/models/{model_hash}/save", json=payload)

    async def unsave_model(self, model_hash: str) -> dict:
        """Release a model's saved slot (#673) — the non-destructive
        inverse of save_model; the model stays addressable by hash."""
        return await self._request("POST", f"/api/v1/models/{model_hash}/unsave")

    async def list_projects(self) -> dict:
        """Projects the caller can file models into (#645): owned + team-shared."""
        return await self._request("GET", "/api/v1/projects")

    async def create_project(self, name: str, team_id: int | None = None) -> dict:
        """Create a named project (#645); 201 with the new project's id."""
        payload: dict = {"name": name}
        if team_id is not None:
            payload["team_id"] = team_id
        return await self._request("POST", "/api/v1/projects", json=payload)

    async def rename_project(self, project_id: int, name: str) -> dict:
        """Rename a project you OWN (#645); team members cannot rename shared folders."""
        return await self._request("PATCH", f"/api/v1/projects/{project_id}", json={"name": name})

    async def get_model(self, model_hash: str) -> dict:
        """Model metadata + config echo (#45); works for every status incl. failed."""
        return await self._request("GET", f"/api/v1/models/{model_hash}")

    async def delete_model(self, model_hash: str) -> dict:
        """Delete a FAILED model (#45); the API 409s for any other status."""
        return await self._request("DELETE", f"/api/v1/models/{model_hash}")

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

    async def get_optimizer_results(self, model_hash: str, run_id: str | None = None) -> dict:
        if run_id:
            return await self._request("GET", f"/api/v1/models/{model_hash}/optimize/runs/{run_id}")
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

    async def get_scenario_results(self, model_hash: str, run_id: str | None = None) -> dict:
        if run_id:
            return await self._request("GET", f"/api/v1/models/{model_hash}/scenario/runs/{run_id}")
        return await self._request("GET", f"/api/v1/models/{model_hash}/scenario")

    # -- Saved-run curation (#576) --

    _RUN_SEGMENT: ClassVar[dict[str, str]] = {"optimizer": "optimize", "scenario": "scenario"}

    @staticmethod
    def _unknown_artifact(artifact: str) -> dict:
        # Structured payload, never a raise: SDK v2 masks raised exceptions
        # to an info-free "Error executing tool ..." at the client, so the
        # recovery guidance must travel in the tool result.
        return {
            "error": f"Unknown artifact '{artifact}'. Expected one of: optimizer, scenario.",
            "_status_code": 400,
        }

    async def update_run(
        self,
        artifact: str,
        model_hash: str,
        run_id: str,
        *,
        name: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Rename / annotate a saved run (#576). Only provided fields change."""
        segment = self._RUN_SEGMENT.get(artifact)
        if segment is None:
            return self._unknown_artifact(artifact)
        payload: dict = {}
        if name is not None:
            payload["name"] = name
        if notes is not None:
            payload["notes"] = notes
        if tags is not None:
            payload["tags"] = tags
        return await self._request(
            "PATCH", f"/api/v1/models/{model_hash}/{segment}/runs/{run_id}", json=payload
        )

    async def set_run_pinned(
        self,
        artifact: str,
        model_hash: str,
        run_id: str,
        pinned: bool | None = None,
    ) -> dict:
        """Pin/unpin a saved run (#576). ``pinned`` sets; None toggles."""
        segment = self._RUN_SEGMENT.get(artifact)
        if segment is None:
            return self._unknown_artifact(artifact)
        kwargs: dict = {}
        if pinned is not None:
            kwargs["json"] = {"pinned": pinned}
        return await self._request(
            "POST", f"/api/v1/models/{model_hash}/{segment}/runs/{run_id}/pin", **kwargs
        )

    async def list_runs(
        self,
        artifact: str,
        model_hash: str,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Run history for a model (#21): GET .../optimize/runs or .../scenario/runs."""
        segment = self._RUN_SEGMENT.get(artifact)
        if segment is None:
            return self._unknown_artifact(artifact)
        return await self._request(
            "GET",
            f"/api/v1/models/{model_hash}/{segment}/runs",
            params={"limit": limit, "offset": offset},
        )

    # -- Upload listing (#21) --

    async def list_uploads(self, limit: int = 50, offset: int = 0, name: str = "") -> dict:
        params: dict = {"limit": limit, "offset": offset}
        if name:
            params["name"] = name
        return await self._request("GET", "/api/v1/ingest", params=params)

    async def get_upload(self, file_id: int) -> dict:
        return await self._request("GET", f"/api/v1/ingest/{file_id}")
