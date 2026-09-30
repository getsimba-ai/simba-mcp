"""Request credentials and local-file access boundary."""

import os
from typing import Any

from mcp.server.mcpserver import Context

from . import runtime
from .api_client import CALLER_API_KEY, SimbaAPIClient


def _http_mode(ctx=None) -> bool:
    if ctx is not None:
        mode = getattr(ctx.request_context.lifespan_context, "serving_http", None)
        if isinstance(mode, bool):
            return mode
    return runtime._serving_http


def local_files_effective(raw: str | None, serving_http: bool) -> tuple[bool, str]:
    """Return whether csv_path is allowed and which rule decided it.

    Unrecognised values follow the transport default. They do not become an
    implicit allow on a network transport.
    """
    env = ("" if raw is None else raw).strip().lower()
    if env in ("1", "true", "yes"):
        return True, "explicit"
    if env in ("0", "false", "no"):
        return False, "explicit"
    if serving_http:
        return False, "network-default"
    return True, "stdio-default"


def _local_files_allowed(ctx=None) -> bool:
    return _local_files_denial_reason(ctx) is None


def _local_files_denial_reason(ctx=None) -> str | None:
    """Return an error message if csv_path reads are disallowed, else None.

    Distinguishes an explicit SIMBA_MCP_ALLOW_LOCAL_FILES=0 from the default
    HTTP/SSE disable, so callers get accurate remediation guidance.
    """
    raw = os.environ.get("SIMBA_MCP_ALLOW_LOCAL_FILES", "")
    allowed, source = local_files_effective(raw, _http_mode(ctx))
    if allowed:
        return None
    if source == "explicit":
        return (
            "csv_path is disabled because SIMBA_MCP_ALLOW_LOCAL_FILES is set "
            f"to {raw.strip().lower()!r}. Pass csv_content instead, or set "
            "SIMBA_MCP_ALLOW_LOCAL_FILES=1 to allow local file reads."
        )
    return (
        "csv_path is disabled on network transports (HTTP/SSE) because "
        "it reads the server host's filesystem, not yours. Pass "
        "csv_content instead, or set SIMBA_MCP_ALLOW_LOCAL_FILES=1 "
        "on the server if this is intentional."
    )


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


def _page(limit=None, cursor=None, expand=None):
    """Query params for bounded, summary-first list reads (jellyfish #824)."""
    params: dict = {"limit": limit, "cursor": cursor}
    if expand:
        params["expand"] = ",".join(expand)
    return params


def _client(ctx: Context[runtime.AppContext, Any]) -> SimbaAPIClient:
    if _http_mode(ctx):
        # Bring-your-own-key (#51): every hosted caller authenticates with
        # their OWN key from this request's Authorization header. Set
        # unconditionally — "" makes every backend call fail with guidance —
        # and deliberately WITHOUT a fallback to the env key: a shared
        # fallback identity is exactly the hole this closes. The ContextVar
        # is task-local, so concurrent callers cannot mix keys.
        CALLER_API_KEY.set(_bearer_token(ctx))
    elif getattr(ctx.request_context.lifespan_context, "serving_http", None) is False:
        CALLER_API_KEY.set(None)
    return ctx.request_context.lifespan_context.client
