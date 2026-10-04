"""Caller-specific hosted tool views; backend permissions remain authoritative."""

import asyncio
import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Mapping
from types import SimpleNamespace

from mcp.types import CallToolResult, TextContent

from .api_client import CALLER_API_KEY
from .auth import _bearer_token
from .errors import api_error
from .profiles import PROFILE_NAMES, PROFILES

logger = logging.getLogger(__name__)
CACHE_SECONDS = 30.0
LOOKUP_SECONDS = 5.0
MAX_CACHE_ENTRIES = 1024
_cache: OrderedDict[tuple[str, str], tuple[float, str]] = OrderedDict()
_lock = threading.Lock()
_next_warning = 0.0


def _cached(identity, now):
    with _lock:
        entry = _cache.get(identity)
        if entry is not None:
            expires, profile = entry
            if expires > now:
                _cache.move_to_end(identity)
                return profile
            del _cache[identity]
    return None


def _remember(identity, profile):
    now = time.monotonic()
    with _lock:
        for key, (expires, _) in list(_cache.items()):
            if expires <= now:
                del _cache[key]
        _cache[identity] = (now + CACHE_SECONDS, profile)
        _cache.move_to_end(identity)
        while len(_cache) > MAX_CACHE_ENTRIES:
            _cache.popitem(last=False)


def _warn_fallback():
    global _next_warning
    now = time.monotonic()
    with _lock:
        if now < _next_warning:
            return
        _next_warning = now + 60.0
    logger.warning("Account tool profile unavailable; using the operator's tool catalogue.")


def _tool_name(tool):
    return tool.get("name") if isinstance(tool, Mapping) else tool.name


class UserProfileMiddleware:
    """Narrow each hosted list/call without mutating registered tools or credentials."""

    async def __call__(self, ctx, call_next):
        app = ctx.lifespan_context
        if ctx.method not in {"tools/list", "tools/call"} or not app.serving_http:
            return await call_next(ctx)
        # SDK 2.1/2.2 middleware uses ServerRequestContext with request.headers;
        # high-level tool contexts expose headers directly. Share bearer parsing.
        headers = getattr(ctx, "headers", None)
        if headers is None:
            headers = getattr(getattr(ctx, "request", None), "headers", None)
        bearer = _bearer_token(SimpleNamespace(headers=headers))
        if not bearer:
            return await call_next(ctx)

        client = app.client
        identity = (client.base_url, hashlib.sha256(bearer.encode()).hexdigest())
        profile = _cached(identity, time.monotonic())
        if profile is None:
            token = CALLER_API_KEY.set(bearer)
            try:
                async with asyncio.timeout(LOOKUP_SECONDS):
                    result = await client._request(
                        "GET", "/api/v1/mcp/preferences", timeout=LOOKUP_SECONDS, retry_safe=False
                    )
            except Exception:  # noqa: BLE001 - approved fallback for any preference failure
                # Preference failure must not take hosted tools offline. Cancellation
                # remains a BaseException and propagates; never log exception payloads.
                result = None
            finally:
                CALLER_API_KEY.reset(token)
            if (
                isinstance(result, dict)
                and result.get("_status_code", 200) == 200
                and type(result.get("schema_version")) is int
                and result["schema_version"] == 1
                and isinstance(result.get("profile"), str)
                and result["profile"] in PROFILE_NAMES
            ):
                profile = result["profile"]
                _remember(identity, profile)
            else:
                # Authentication failures flow to the existing tool/backend refusal.
                if not isinstance(result, dict) or result.get("_status_code") != 401:
                    _warn_fallback()
                return await call_next(ctx)

        if profile in {"full", "data_scientist"}:
            return await call_next(ctx)
        allowed = PROFILES[profile]
        if ctx.method == "tools/call":
            params = ctx.params
            # Leave malformed protocol requests to the SDK's normal validation.
            if (
                isinstance(params, Mapping)
                and isinstance(params.get("name"), str)
                and params["name"] not in allowed
            ):
                payload = api_error(
                    403,
                    {
                        "error": "This tool is excluded by your account's tool profile.",
                        "code": "profile_excluded",
                        "profile": profile,
                        "_next_action": (
                            "Change the tool profile under Profile > Connected apps, or choose "
                            "Full. Wait up to a minute, then reconnect your assistant. "
                            "Reconcile any uncertain write before retrying."
                        ),
                    },
                )
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(payload))],
                    structured_content=payload,
                    is_error=True,
                )
            return await call_next(ctx)

        result = await call_next(ctx)
        if isinstance(result, dict):
            return {**result, "tools": [t for t in result["tools"] if _tool_name(t) in allowed]}
        return result.model_copy(update={"tools": [t for t in result.tools if t.name in allowed]})
