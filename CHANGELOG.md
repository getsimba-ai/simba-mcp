# Changelog

All notable changes to the SIMBA MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## Unreleased

### Added

- `upload_data` accepts `csv_path` (mutually exclusive with `csv_content`): the server reads the file directly, so large CSVs no longer transit the LLM conversation. Pre-flight existence/size checks; dataset name defaults to the file stem. Local (stdio) servers only — disabled on HTTP/SSE transports unless `SIMBA_MCP_ALLOW_LOCAL_FILES=1` (issue #14).

### Fixed

- Upload size limit corrected: the API enforces **10 MB**, not the previously documented 50 MB. Docstring and README updated; oversized `csv_path` uploads fail fast with a clear message (issue #14).
- Row-minimum guidance no longer hardcodes "52 rows" — it defers to `get_data_schema` → `x-simba-constraints.min_rows` and notes that the upload response's `warnings` field is authoritative (issue #14).

## 0.1.2 — 2026-04-06

### Added

- Enriched MCP tool descriptions with inline gotchas (channel name matching, array requirements, NaN cleaning, async polling patterns) so AI agents get tips automatically.
- README: Gotchas & Tips section covering the 6 most common pitfalls.
- README: Common Errors table with causes and fixes.
- README: Direct API Access section with MCP vs API comparison, Python and curl quick-start examples.

## 0.1.1 — 2026-04-06

### Fixed

- Updated API URL in README examples from `app.getsimba.ai` to `demo.simba-mmm.com` (Cursor IDE, Claude Code, and Claude API connector configs).

## 0.1.0 — 2026-04-05

### Added

- Initial release of the SIMBA MCP Server.
- 11 MCP tools: `get_data_schema`, `upload_data`, `list_models`, `create_model`, `get_model_status`, `get_model_results`, `run_optimizer`, `get_optimizer_results`, `get_scenario_template`, `run_scenario`, `get_scenario_results`.
- Async HTTP client (`SimbaAPIClient`) wrapping Simba API v1.
- Support for stdio, Streamable HTTP, and SSE transport modes.
- CLI entrypoint (`simba-mcp`).
- CI workflow (lint + test on Python 3.11/3.12/3.13).
- PyPI publish workflow on GitHub Release.
