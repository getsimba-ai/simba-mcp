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
    else:
        set_http_mode(True)
        # v2 moved host/port off Settings onto the per-transport run kwargs.
        mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
