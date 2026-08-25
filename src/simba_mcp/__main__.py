"""
Entry point for running the Simba MCP server.

Usage:
    # stdio mode (for Cursor, Claude Code local config):
    simba-mcp

    # Streamable HTTP mode (for remote deployment):
    simba-mcp --transport streamable-http --port 8100

    # Or via uvicorn directly:
    uvicorn simba_mcp.server:app --host 0.0.0.0 --port 8100
"""

import argparse

from .server import mcp, set_http_mode


def main():
    parser = argparse.ArgumentParser(description="SIMBA MCP Server")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "streamable-http", "sse"],
        help="MCP transport mode (default: stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8100, help="Port to bind (default: 8100)")
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "streamable-http":
        set_http_mode(True)
        # v2 moved transport config off the shared Settings onto per-transport
        # run kwargs, so stateless_http/json_response no longer inherit from
        # the constructor: pass them here too or the CLI HTTP path silently
        # reverts to stateful sessions, unlike the deployed ASGI app.
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            json_response=True,
            stateless_http=True,
        )
    else:  # sse (no stateless/json knobs on this transport)
        set_http_mode(True)
        mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
