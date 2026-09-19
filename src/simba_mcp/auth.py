"""Request credentials and local-file access boundary."""

import os
from typing import Any

from mcp.server.mcpserver import Context

from . import runtime
from .api_client import CALLER_API_KEY, SimbaAPIClient


def _local_files_allowed() -> bool:
    return _local_files_denial_reason() is None


def _local_files_denial_reason() -> str | None:
    """Return an error message if csv_path reads are disallowed, else None.

    Distinguishes an explicit SIMBA_MCP_ALLOW_LOCAL_FILES=0 from the default
    HTTP/SSE disable, so callers get accurate remediation guidance.
    """
    env = os.environ.get("SIMBA_MCP_ALLOW_LOCAL_FILES", "").strip().lower()
    if env in ("1", "true", "yes"):
        return None
    if env in ("0", "false", "no"):
        return (
            "csv_path is disabled because SIMBA_MCP_ALLOW_LOCAL_FILES is set "
            f"to {env!r}. Pass csv_content instead, or set "
            "SIMBA_MCP_ALLOW_LOCAL_FILES=1 to allow local file reads."
        )
    if runtime._serving_http:
        return (
            "csv_path is disabled on network transports (HTTP/SSE) because "
            "it reads the server host's filesystem, not yours. Pass "
            "csv_content instead, or set SIMBA_MCP_ALLOW_LOCAL_FILES=1 "
            "on the server if this is intentional."
        )
    return None


def _bearer_token(ctx: Context[runtime.AppContext, Any]) -> str:
    """The caller's bearer token from this request's Authorization header.

    Returns "" when the header is absent or malformed — never a fallback
    credential. Header lookup is case-insensitive (HTTP/2 lowercases).
    """
    headers = getattr(ctx, "headers", None) or {}
    for name, value in headers.items():
        if name.lower() == "authorization":
            scheme, _, token = value.partition(" ")
            if scheme.lower() == "bearer" and token.strip():
                return token.strip()
            return ""
    return ""


def _client(ctx: Context[runtime.AppContext, Any]) -> SimbaAPIClient:
    if runtime._serving_http:
        # Bring-your-own-key (#51): every hosted caller authenticates with
        # their OWN key from this request's Authorization header. Set
        # unconditionally — "" makes every backend call fail with guidance —
        # and deliberately WITHOUT a fallback to the env key: a shared
        # fallback identity is exactly the hole this closes. The ContextVar
        # is task-local, so concurrent callers cannot mix keys.
        CALLER_API_KEY.set(_bearer_token(ctx))
    return ctx.request_context.lifespan_context.client
