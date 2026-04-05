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

from .server import mcp


def main():
    parser = argparse.ArgumentParser(description="Simba MCP Server")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "streamable-http", "sse"],
        help="MCP transport mode (default: stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8100, help="Port to bind (default: 8100)")
    args = parser.parse_args()

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
