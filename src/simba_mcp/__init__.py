"""Simba MCP Server — connect AI assistants to Simba MMM."""

__version__ = "0.1.0"

from .api_client import SimbaAPIClient
from .server import create_app, mcp

__all__ = ["SimbaAPIClient", "create_app", "mcp"]
