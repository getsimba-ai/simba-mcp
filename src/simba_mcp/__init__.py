"""Simba MCP Server — connect AI assistants to Simba MMM."""

__version__ = "0.18.0"

from .api_client import SimbaAPIClient


def __getattr__(name):
    # Keep the public singleton import while allowing diagnostic commands to
    # inspect invalid settings before server construction validates them.
    if name == "mcp":
        from .server import mcp

        return mcp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["SimbaAPIClient", "mcp"]
