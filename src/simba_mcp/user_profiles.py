"""Apply authenticated user tool preferences without mutating the shared catalogue."""

import asyncio

from mcp.shared.exceptions import MCPError

from .api_client import CALLER_API_KEY
from .profiles import PROFILE_NAMES, PROFILES

PREFERENCE_LOOKUP_SECONDS = 5.0


class UserProfileMiddleware:
    """Resolve preferences on each HTTP tool request; backend permissions stay definitive.

    No cross-caller preference cache is kept. The coordinated backend contract
    is required; all lookup failures, including 404, fail closed.
    """

    async def __call__(self, ctx, call_next):
        if ctx.method not in {"tools/list", "tools/call"}:
            return await call_next(ctx)
        app = ctx.lifespan_context
        if not getattr(app, "serving_http", False):
            return await call_next(ctx)
        headers = getattr(ctx.request, "headers", {}) or {}
        auth = next((v for k, v in headers.items() if k.lower() == "authorization"), "")
        scheme, _, credential = auth.partition(" ")
        if scheme.lower() != "bearer" or not credential.strip():
            raise MCPError(-32000, "Authentication required for tool preferences")
        token = CALLER_API_KEY.set(credential.strip())
        try:
            async with asyncio.timeout(PREFERENCE_LOOKUP_SECONDS):
                preference = await app.client._request(
                    "GET", "/api/v1/mcp/preferences", retry_safe=False
                )
        except Exception as exc:
            raise MCPError(
                -32000, "Unable to resolve tool preferences; retry or reconnect"
            ) from exc
        finally:
            CALLER_API_KEY.reset(token)
        if not isinstance(preference, dict):
            raise MCPError(-32000, "Unable to resolve tool preferences; retry or reconnect")
        profile = preference.get("profile")
        if (
            type(preference.get("_status_code", 200)) is not int
            or preference.get("_status_code", 200) != 200
            or type(preference.get("schema_version")) is not int
            or preference.get("schema_version") != 1
            or profile not in PROFILE_NAMES
        ):
            raise MCPError(-32000, "Unable to resolve tool preferences; retry or reconnect")
        allowed = PROFILES.get(profile)
        if (
            ctx.method == "tools/call"
            and allowed is not None
            and (ctx.params or {}).get("name") not in allowed
        ):
            raise MCPError(
                -32000,
                "Tool is outside your selected profile; change Agent connections settings and reconnect",
            )
        result = await call_next(ctx)
        if ctx.method == "tools/list" and allowed is not None:
            # Create a response-local copy. Never edit server registrations or another response.
            if isinstance(result, dict):
                result = {**result, "tools": [t for t in result["tools"] if t["name"] in allowed]}
            else:
                result = result.model_copy(
                    update={"tools": [t for t in result.tools if t.name in allowed]}
                )
        return result
