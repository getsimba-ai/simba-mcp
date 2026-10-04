"""Synthetic Full-account metadata for wire tests of unrelated tool contracts."""

import inspect

import httpx


def hosted_transport(tool_handler):
    """Keep exact tool-exchange assertions separate from the account metadata read."""

    async def handle(request):
        if request.method == "GET" and request.url.path == "/api/v1/mcp/preferences":
            return httpx.Response(200, json={"schema_version": 1, "profile": "full"})
        result = tool_handler(request)
        return await result if inspect.isawaitable(result) else result

    return httpx.MockTransport(handle)
