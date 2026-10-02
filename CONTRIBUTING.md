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

For catalogue and synthetic request measurements, see
[Measuring MCP performance](docs/performance.md). Metrics are opt-in and the
offline commands require no Simba account or model-provider credentials.

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


### Module ownership and contract changes

Every issue and PR must follow the [engineering objective](docs/engineering.md):
record package ownership, reuse and dependency direction at pickup, and include an
architecture note at review. For performance epic #38 this is a standing acceptance gate.

Add plain async functions to a domain module in `src/simba_mcp/tools/`, export and
register them in `server.py`, and explicitly classify their effects in
`metadata.py`. Registration fails for an unclassified tool. Keep business rules
and durable workflow state in the backend. Use permissive schema descriptions to
preserve newer backend fields; do not copy backend validators into MCP.

Update the input-schema snapshot only for intentional, documented contract
changes. Test the actual MCP wire result as well as direct Python forwarding.
Run `pytest`, `ruff check src/ tests/`, `ruff format --check src/ tests/`, and
`uv build`. Verify the supported SDK floor separately when changing SDK-facing
contracts. See [architecture](docs/architecture.md) for compatibility boundaries.

Run `python -m simba_mcp.evaluation --samples 3 --output-dir .codex/evaluation`
for deterministic workflow contracts. The [evaluation guide](docs/evaluation.md)
describes synthetic cases, measurements and separate model-evaluation gates.

### Role, guidance and example maintenance

Every tool change needs a job-based inclusion/exclusion decision for marketer and
reviewer in packaged `guidance/content/coverage.json`. Runtime registration and
`profiles.py` remain canonical; coverage is maintenance evidence, not another
runtime registry. Record required dependencies, guidance topic and an executable
example or an explicit reason no standalone example is needed. Roles never grant
backend permissions; distinguish audit-producing reads and read-only POST calculations.

Use existing Case/Step/Exchange contracts and run_case for synthetic examples in
`evaluation/role_workflows.py`. Keep existing paid-trial definitions/reports frozen.
Edit canonical guidance, increment its shared version and regenerate in this order:

```shell
python -m simba_mcp.reference
python -m simba_mcp.guidance.coverage
python -m simba_mcp.guidance
python -m simba_mcp.guidance.coverage --check
python -m simba_mcp.guidance --check
python -m simba_mcp.evaluation --roles --description-mode compact --output-dir .codex/evaluation/roles
```

Coverage checks catch unclassified tools, stale current counts, role dependencies
and invalid example schemas; focused negative tests also exercise broken links and
forbidden writes. Historical counts stay dated. Include public synthetic evidence
and exact release/client limitations, never customer data or credentials.
