"""
Async HTTP client for the Simba API v1.

Wraps all API v1 endpoints so MCP tools stay thin and declarative.
"""

import asyncio
import contextvars
import json
import logging
import zlib
from typing import Any, ClassVar

import httpx

from . import telemetry
from .errors import api_error

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60.0
MAX_RETRIES = 3
BACKOFF_BASE = 0.5
RESPONSE_STREAM_CHUNK_BYTES = 64 * 1024
RETRIABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

AUTH_HELP = (
    "This MCP server requires a Simba account. "
    "Start free at https://demo.simba-mmm.com/users/signup, then create an API key at "
    "Profile > API Keys in the Simba UI. "
    "Prefer a walkthrough? Book a demo: https://calendly.com/niall-oulton"
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


class ResponseReadError(Exception):
    """A response could not be safely decoded within the configured contract."""

    def __init__(self, message: str, *, status_code: int = 413, limit_name: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.limit_name = limit_name


class SimbaAPIClient:
    """Thin async wrapper around Simba's API v1 endpoints."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        max_encoded_bytes: int | None = None,
        max_decoded_bytes: int | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client: httpx.AsyncClient | None = None
        # Limits are opt-in until production response-size baselines are approved.
        # If one ceiling is configured, apply it to both representations so a
        # compressed response cannot bypass the only configured bound.
        for name, value in (
            ("max_encoded_bytes", max_encoded_bytes),
            ("max_decoded_bytes", max_decoded_bytes),
        ):
            if value is not None and (type(value) is not int or value <= 0):
                raise ValueError(f"{name} must be a positive integer or None")
        self.max_encoded_bytes = (
            max_encoded_bytes if max_encoded_bytes is not None else max_decoded_bytes
        )
        self.max_decoded_bytes = (
            max_decoded_bytes if max_decoded_bytes is not None else max_encoded_bytes
        )

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

    async def _parse_response(
        self, response: httpx.Response, body: bytes | None = None
    ) -> dict[str, Any]:
        if body is None:
            body = await response.aread()
        if response.status_code >= 400:
            try:
                error_body = json.loads(body)
            except ValueError:
                # Non-JSON error body (HTML gateway pages, plain text)
                error_body = None
            error_body = api_error(response.status_code, error_body)
            if response.status_code in (401, 403):
                error_body["_help"] = AUTH_HELP
            return error_body
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type.lower():
            # e.g. GET .../results?format=csv returns text/csv
            return {
                "format": "csv",
                "content": body.decode(response.encoding or "utf-8", errors="replace"),
            }
        try:
            payload = json.loads(body)
        except ValueError:
            return api_error(502, {"error": "Backend returned invalid JSON."})
        if not isinstance(payload, dict):
            return api_error(502, {"error": "Backend returned a non-object JSON response."})
        return payload

    async def _read_response_body(
        self, response: httpx.Response, observation: telemetry.Attempt | None
    ) -> bytes:
        """Read a response incrementally, enforcing encoded and decoded ceilings."""
        encoded_limit = self.max_encoded_bytes
        decoded_limit = self.max_decoded_bytes
        if encoded_limit is None and decoded_limit is None:
            # Preserve HTTPX's negotiated encodings and decoder behaviour when
            # transport limits have not been enabled.
            body = await response.aread()
            if observation is not None:
                observation.body_bytes(downloaded=response.num_bytes_downloaded, decoded=len(body))
            return body
        # A custom transport may hand HTTPX an already consumed, decompressed
        # body. Its encoded size and content-encoding can no longer be verified,
        # so do not claim that configured transport limits were enforced.
        if response.is_stream_consumed:
            if encoded_limit is not None:
                raise ResponseReadError(
                    "Cannot enforce the configured encoded-byte limit because the response was buffered before the bounded reader received it.",
                    status_code=502,
                )
            body = response.content
            if decoded_limit is not None and len(body) > decoded_limit:
                raise ResponseReadError(
                    f"Backend response exceeded the configured decoded-byte limit ({decoded_limit} bytes).",
                    limit_name="decoded_bytes",
                )
            if observation is not None:
                observation.body_bytes(decoded=len(body))
            return body
        content_length = response.headers.get("content-length")
        if (
            encoded_limit is not None
            and content_length
            and content_length.isdecimal()
            and int(content_length) > encoded_limit
        ):
            raise ResponseReadError(
                f"Backend response Content-Length exceeds the configured encoded-byte limit ({encoded_limit} bytes).",
                limit_name="encoded_bytes",
            )

        codings = [
            item.strip().lower()
            for item in response.headers.get("content-encoding", "identity").split(",")
            if item.strip() and item.strip().lower() != "identity"
        ]
        if len(codings) > 1 or (codings and codings[0] not in {"gzip", "x-gzip", "deflate"}):
            raise ResponseReadError(
                "Backend used a compression encoding that this bounded reader cannot safely decode.",
                status_code=502,
            )
        decoder = None
        if codings:
            window = zlib.MAX_WBITS | 16 if codings[0] in {"gzip", "x-gzip"} else zlib.MAX_WBITS
            decoder = zlib.decompressobj(window)

        body = bytearray()
        encoded_count = 0
        first_decode = True
        decoded_count = 0
        chunks = response.aiter_raw(chunk_size=RESPONSE_STREAM_CHUNK_BYTES)
        async for chunk in chunks:
            encoded_count += len(chunk)
            if observation is not None:
                observation.body_bytes(downloaded=len(chunk))
            if encoded_limit is not None and encoded_count > encoded_limit:
                raise ResponseReadError(
                    f"Backend response exceeded the configured encoded-byte limit ({encoded_limit} bytes).",
                    limit_name="encoded_bytes",
                )
            try:
                remaining = decoded_limit - decoded_count + 1 if decoded_limit is not None else 0
                try:
                    decoded = decoder.decompress(chunk, remaining) if decoder else chunk
                except zlib.error:
                    # HTTP deflate servers use both zlib-wrapped and raw streams.
                    # Retry only the first chunk, retaining the same output cap.
                    if not first_decode or codings != ["deflate"]:
                        raise
                    decoder = zlib.decompressobj(-zlib.MAX_WBITS)
                    decoded = decoder.decompress(chunk, remaining)
                first_decode = False
            except zlib.error as exc:
                raise ResponseReadError(
                    "Backend returned an invalid compressed response.", status_code=502
                ) from exc
            next_decoded_count = decoded_count + len(decoded)
            if decoded_limit is not None and next_decoded_count > decoded_limit:
                raise ResponseReadError(
                    f"Backend response exceeded the configured decoded-byte limit ({decoded_limit} bytes).",
                    limit_name="decoded_bytes",
                )
            if decoder and decoder.unconsumed_tail:
                raise ResponseReadError(
                    f"Backend response exceeded the configured decoded-byte limit ({decoded_limit} bytes).",
                    limit_name="decoded_bytes",
                )
            body.extend(decoded)
            decoded_count = next_decoded_count

        if decoder:
            if not decoder.eof:
                raise ResponseReadError(
                    "Backend returned an incomplete compressed response.", status_code=502
                )
            if decoder.unused_data:
                raise ResponseReadError(
                    "Backend returned trailing or concatenated compressed data that cannot be validated safely.",
                    status_code=502,
                )
            remaining = decoded_limit - decoded_count + 1 if decoded_limit is not None else 0
            try:
                tail = decoder.flush(remaining) if decoded_limit is not None else decoder.flush()
            except zlib.error as exc:
                raise ResponseReadError(
                    "Backend returned an invalid compressed response.", status_code=502
                ) from exc
            next_decoded_count = decoded_count + len(tail)
            if decoded_limit is not None and next_decoded_count > decoded_limit:
                raise ResponseReadError(
                    f"Backend response exceeded the configured decoded-byte limit ({decoded_limit} bytes).",
                    limit_name="decoded_bytes",
                )
            body.extend(tail)
        if observation is not None:
            # Count decoded bytes only once the complete body has passed the
            # transport checks and is about to be supplied to the parser.
            observation.body_bytes(decoded=len(body))
        return bytes(body)

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        attempts = MAX_RETRIES if kwargs.pop("retry_safe", method.upper() in {"GET", "HEAD"}) else 1
        caller_key = CALLER_API_KEY.get()
        if caller_key is None:
            # stdio / no override: the env-configured key is the user's own.
            if not self._api_key:
                return api_error(
                    401,
                    {
                        "error": "SIMBA_API_KEY is not set. " + AUTH_HELP,
                        "_status_code": 401,
                        "_help": AUTH_HELP,
                    },
                )
        elif not caller_key:
            return api_error(
                401,
                {
                    "error": "No API key on this request. " + HTTP_AUTH_HELP,
                    "_status_code": 401,
                    "_help": HTTP_AUTH_HELP,
                },
            )
        else:
            # Per-request header beats the client-default Authorization in
            # httpx, so the shared connection pool is safe to reuse.
            kwargs["headers"] = {
                **kwargs.get("headers", {}),
                "Authorization": f"Bearer {caller_key}",
            }
        client = await self._get_client()
        if self.max_encoded_bytes is not None:
            kwargs["headers"] = {
                "Accept-Encoding": "gzip, deflate",
                **kwargs.get("headers", {}),
            }
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                with telemetry.backend_attempt(method, path) as observation:
                    async with client.stream(method, path, **kwargs) as response:
                        if observation is not None:
                            observation.response(response)
                        if (
                            response.status_code in RETRIABLE_STATUS_CODES
                            and attempt < attempts - 1
                        ):
                            retry_status = response.status_code
                            body = None
                        else:
                            retry_status = None
                            body = await self._read_response_body(response, observation)
                            with telemetry.phase("http_parse"):
                                return await self._parse_response(response, body)
                if retry_status is not None:
                    delay = BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        "Retryable %d from %s (attempt %d/%d, retrying in %.1fs)",
                        retry_status,
                        method,
                        attempt + 1,
                        attempts,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
            except ResponseReadError as exc:
                if observation is not None:
                    observation.refused()
                payload = {
                    "error": str(exc),
                    "_status_code": exc.status_code,
                    "_next_action": (
                        "Request fewer result sections/channels or a smaller window. "
                        "Use a supported external export path for full results; no partial evidence was returned."
                    ),
                }
                if exc.limit_name:
                    payload["limit"] = exc.limit_name
                return api_error(exc.status_code, payload)
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt < attempts - 1:
                    delay = BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        "Transport error on %s (attempt %d/%d, retrying in %.1fs): %s",
                        method,
                        attempt + 1,
                        attempts,
                        delay,
                        type(exc).__name__,
                    )
                    await asyncio.sleep(delay)
        # Return a structured payload like every other failure mode instead of
        # raising: SDK v2 masks unexpected exceptions to an info-free
        # "Error executing tool ..." at the client, which would hide the most
        # plausible production failure (backend unreachable during a deploy).
        return api_error(
            503,
            {
                "error": (
                    f"Simba API unreachable after {attempts} attempts "
                    f"({type(last_exc).__name__}). The backend may be "
                    "restarting or the SIMBA_API_URL may be wrong. Check _next_action before retrying."
                ),
                "_status_code": 503,
            },
        )

    # -- Ingest --

    async def get_schema(self) -> dict:
        return await self._request("GET", "/api/v1/ingest/schema")

    async def upload_csv(
        self, csv_content: str, name: str = "", filename: str = "", roles: dict | None = None
    ) -> dict:
        """Upload CSV text content. For MCP, CSV arrives as a string."""
        params = {}
        if name:
            params["name"] = name
        if filename:
            params["filename"] = filename
        if roles:
            params["roles"] = json.dumps(roles)
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

    async def link_var_model(
        self,
        model_hash: str,
        var_model_hash: str,
        channel_map: dict[str, list[str]] | None = None,
    ) -> dict:
        body: dict = {"var_model_hash": var_model_hash}
        if channel_map is not None:
            body["channel_map"] = channel_map
        return await self._request(
            "POST",
            f"/api/v1/models/{model_hash}/link_var",
            json=body,
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
        start: str = "",
        end: str = "",
        granularity: str = "",
    ) -> dict:
        params: dict[str, str] = {"format": fmt}
        if sections:
            params["sections"] = sections
        for key, value in (("start", start), ("end", end), ("granularity", granularity)):
            if value:
                params[key] = value
        return await self._request(
            "GET",
            f"/api/v1/models/{model_hash}/results",
            params=params,
        )

    # -- Datasets --

    async def get_data_report(self, dataset_id: int, params: dict[str, str]) -> dict:
        return await self._request("GET", f"/api/v1/datasets/{dataset_id}/report", params=params)

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
        return api_error(
            400,
            {
                "error": f"Unknown artifact '{artifact}'. Expected one of: optimizer, scenario.",
                "_status_code": 400,
            },
        )

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

    async def workflow_request(
        self, method: str, path: str, payload: dict | None = None, params: dict | None = None
    ) -> dict:
        """Internal adapter for fixed workflow routes; writes are never auto-retried."""
        kwargs: dict = {} if payload is None else {"json": payload}
        if params:
            kwargs["params"] = {k: v for k, v in params.items() if v is not None and v != []}
        return await self._request(method, "/api/v1" + path, retry_safe=method == "GET", **kwargs)
