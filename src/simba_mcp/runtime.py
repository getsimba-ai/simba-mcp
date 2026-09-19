"""Shared process lifecycle and SDK transport configuration."""

import importlib.metadata
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.mcpserver import MCPServer

from .api_client import SimbaAPIClient

logger = logging.getLogger(__name__)
MAX_REQUEST_BODY_BYTES = 12 * 1024 * 1024


@dataclass
class AppContext:
    client: SimbaAPIClient


@asynccontextmanager
async def app_lifespan(server: MCPServer) -> AsyncIterator[AppContext]:
    # Under SDK v2's streamable HTTP the lifespan enters ONCE per process and
    # this AppContext is shared by every session (v1 entered it per-session).
    # Safe here: the client holds a stateless httpx connection pool, and in
    # HTTP mode each request's credential rides a task-local ContextVar
    # (#51), never the shared client — no per-session state may ever be
    # added to AppContext without revisiting this.
    from .auth import is_http_mode

    base_url = os.environ.get("SIMBA_API_URL", "http://localhost:5005")
    api_key = os.environ.get("SIMBA_API_KEY", "")
    if is_http_mode():
        # BYOK (#51): callers bring their own key; the env key is unused.
        logger.info(
            "HTTP mode: per-caller Authorization bearer tokens authenticate "
            "every request (bring-your-own-key); SIMBA_API_KEY is not used."
        )
        # Fail closed at the boundary, not just at _client(): the shared
        # client gets NO default credential in HTTP mode, so any code path
        # that ever bypasses _client(ctx) hits the empty-key 401 instead of
        # silently authenticating as a shared env identity (#51 review).
        api_key = ""
    elif not api_key:
        logger.warning(
            "SIMBA_API_KEY is not set — all API calls will return an authentication error. "
            "This MCP server requires a Simba account. "
            "Book a call to get started: https://calendly.com/niall-oulton"
        )
    client = SimbaAPIClient(base_url, api_key)
    try:
        yield AppContext(client=client)
    finally:
        await client.close()


def _own_version() -> str:
    """simba-mcp's own package version for the initialize handshake (#41).

    v2 servers with no version report "" — not the SDK fallback — so losing
    this kwarg would silently regress #41 in a new way.
    """
    try:
        return importlib.metadata.version("simba-mcp")
    except importlib.metadata.PackageNotFoundError:  # running from source without install
        return "0.0.0"


def create_app(mcp: MCPServer):
    """Create the ASGI app for uvicorn/Streamable HTTP deployment."""
    from .auth import set_http_mode

    set_http_mode(True)
    # host="0.0.0.0" opts out of the SDK's auto-enabled DNS-rebinding
    # protection (it activates when host is localhost-ish): this app runs
    # behind a reverse proxy with a public Host header, which the localhost
    # allowlist would reject.
    return mcp.streamable_http_app(
        streamable_http_path="/",
        json_response=True,
        stateless_http=True,
        host="0.0.0.0",
        # Front proxies must allow at least the same (nginx
        # client_max_body_size), or they reject the upload first.
        max_request_body_size=MAX_REQUEST_BODY_BYTES,
    )
