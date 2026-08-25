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

from .server import MAX_REQUEST_BODY_BYTES, mcp, set_http_mode


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
        # run kwargs, so nothing inherits from the constructor: every option
        # the deployed ASGI app sets must be repeated here, or the CLI HTTP
        # path silently diverges (stateful sessions, 4 MiB body cap).
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            json_response=True,
            stateless_http=True,
            max_request_body_size=MAX_REQUEST_BODY_BYTES,
        )
    else:  # sse (no stateless/json knobs on this transport)
        set_http_mode(True)
        mcp.run(
            transport="sse",
            host=args.host,
            port=args.port,
            max_request_body_size=MAX_REQUEST_BODY_BYTES,
        )


if __name__ == "__main__":
    main()
