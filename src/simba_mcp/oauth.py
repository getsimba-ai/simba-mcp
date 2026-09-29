"""Optional OAuth resource-server mode (issue #59).

With ``MCP_OAUTH_ENABLED`` set, the server runs in the SDK's resource-server mode: it serves the
protected-resource metadata, answers 401 with ``WWW-Authenticate … resource_metadata=`` to any
request without a verified bearer, and verifies each bearer by asking the backend's token-info
route **with that same bearer**. The server never issues tokens and holds no secret. Both OAuth
access tokens and API keys verify, so key-based clients keep working with the flag on. The
verified token is forwarded to the backend unchanged: the MCP and the API are one protected
resource with one audience.

With the flag off (the default) nothing here is used.
"""

import hashlib
import logging
import os
import time
from datetime import UTC, datetime

import httpx
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60
TOKEN_INFO_PATH = "/api/v1/auth/token-info"


def oauth_enabled() -> bool:
    return os.environ.get("MCP_OAUTH_ENABLED", "").strip().lower() in ("1", "true", "yes")


def public_url() -> str:
    """The issuer and resource base, e.g. https://demo.simba-mmm.com (SIMBA_PUBLIC_URL)."""
    return os.environ.get("SIMBA_PUBLIC_URL", "http://localhost:8100").rstrip("/")


def auth_settings() -> AuthSettings:
    base = public_url()
    return AuthSettings(issuer_url=base, resource_server_url=f"{base}/mcp", required_scopes=None)


def _expires_at(value) -> int | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))  # Python 3.11 accepts a trailing Z
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp())


class BackendTokenVerifier:
    """``TokenVerifier`` that asks the backend what a bearer is, with the bearer itself.

    Positive answers are cached for 60 seconds under a hash of the token; negative answers are
    not cached. A backend timeout or 5xx is ``None`` (a 401 to the client), never an exception.
    """

    def __init__(
        self, base_url: str, *, timeout: float = 5.0, client: httpx.AsyncClient | None = None
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client
        self._cache: dict[str, tuple[float, AccessToken]] = {}

    def _cached(self, key: str) -> AccessToken | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        expires, token = entry
        if expires < time.monotonic():
            self._cache.pop(key, None)
            return None
        return token

    async def _fetch(self, token: str) -> httpx.Response:
        if self._client is not None:
            return await self._client.get(
                f"{self._base_url}{TOKEN_INFO_PATH}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self._timeout,
            )
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.get(
                f"{self._base_url}{TOKEN_INFO_PATH}", headers={"Authorization": f"Bearer {token}"}
            )

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token:
            return None
        key = hashlib.sha256(token.encode("utf-8")).hexdigest()
        cached = self._cached(key)
        if cached is not None:
            return cached
        try:
            response = await self._fetch(token)
        except httpx.HTTPError as exc:
            logger.warning("token-info unreachable: %s", type(exc).__name__)
            return None
        if response.status_code != 200:
            return None
        try:
            info = response.json()
        except ValueError:
            return None
        principal = info.get("principal") or {}
        access = AccessToken(
            token=token,
            client_id=str(
                info.get("client_id") or info.get("key_prefix") or info.get("kind") or "api_key"
            ),
            scopes=list(info.get("scopes") or []),
            expires_at=_expires_at(info.get("expires_at")),
            resource=info.get("resource") or public_url(),
            subject=str(principal.get("user_id")) if principal.get("user_id") is not None else None,
            claims={"kind": info.get("kind")},
        )
        ttl = CACHE_TTL_SECONDS
        if access.expires_at is not None:
            ttl = max(0, min(ttl, access.expires_at - int(time.time())))
        if ttl > 0:
            self._cache[key] = (time.monotonic() + ttl, access)
        return access


def server_auth_options(api_url: str) -> dict:
    """The ``MCPServer`` kwargs the flag adds; an empty dict with the flag off."""
    if not oauth_enabled():
        return {}
    return {"auth": auth_settings(), "token_verifier": BackendTokenVerifier(api_url)}
