# Contributing to SIMBA MCP Server

Thanks for your interest in contributing! This guide covers the basics for getting set up and submitting changes.

For broader contribution guidelines across the SIMBA project, see the [main repo's contributing guide](https://github.com/getsimba-ai/simba-mmm/blob/main/CONTRIBUTING.md).

## Development Setup

```bash
# Clone the repo
git clone https://github.com/getsimba-ai/simba-mcp.git
cd simba-mcp

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install the package in editable mode with dev dependencies
pip install -e ".[dev]"
```

### MCP SDK notes

This server targets MCP Python SDK v2 (`mcp>=2.1,<3` — `MCPServer`, not the
removed `mcp.server.fastmcp`). When changing anything SDK-facing (transports,
`Context` signatures, the constructor, the ASGI app), prefer the official
[`mcp-server-dev` Claude Code plugin](https://github.com/modelcontextprotocol)
skills and the [v2 migration guide](https://py.sdk.modelcontextprotocol.io/v2/migration/)
over folklore in old diffs. Two v2 traps worth knowing: the constructor's
positional order is `(name, title, description, instructions, ...)` — keep
every argument keyword — and `streamable_http_app()` auto-enables DNS-rebinding
protection when its `host` is localhost-ish, which a proxied deployment must
opt out of (see `_create_app`).

## Running Tests

```bash
pytest -v
```

## Linting

```bash
ruff check src/ tests/
```

## Submitting Changes

1. Fork the repo and create a feature branch from `main`.
2. Make your changes — add tests for new functionality.
3. Ensure `pytest -v` and `ruff check src/ tests/` pass locally.
4. Open a pull request against `main` with a clear description of the change.

## Code Style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting, configured in `pyproject.toml` (Python 3.11+, 100-char line length). CI enforces this on every PR.
