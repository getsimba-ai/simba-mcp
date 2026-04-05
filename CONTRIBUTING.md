# Contributing to Simba MCP Server

Thanks for your interest in contributing! This guide covers the basics for getting set up and submitting changes.

For broader contribution guidelines across the Simba project, see the [main repo's contributing guide](https://github.com/getsimba-ai/simba-mmm/blob/main/CONTRIBUTING.md).

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
