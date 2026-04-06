"""Simba MCP Server — connect AI assistants to Simba MMM."""

__version__ = "0.1.2"

from .api_client import SimbaAPIClient
from .server import mcp

__all__ = ["SimbaAPIClient", "mcp"]
