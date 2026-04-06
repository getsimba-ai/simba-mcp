"""Simba MCP Server — connect AI assistants to Simba MMM."""

__version__ = "0.1.2"

from .api_client import SimbaAPIClient
from .server import app, mcp

__all__ = ["SimbaAPIClient", "app", "mcp"]
