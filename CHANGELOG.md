# Changelog

All notable changes to the SIMBA MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## Unreleased

### Fixed

- `get_model_results` docstring now documents all 14 API sections — previously `saturation`, `mroi_summary`, and `long_run_rollup` were undiscoverable — with per-section semantics (issue #12).
- `contributions` vs `coefficients` clarified: contributions are KPI/unit space (multiplier not applied); `coefficients` is the per-period per-channel revenue table.
- Channel-naming rule stated precisely in `get_model_results`, `run_optimizer`, and `run_scenario`: results/template keys are the channel's activity-column name, not `channels[].name`; plus a note that record dates are millisecond epoch integers.
- README: updated the channel-names gotcha and added a Results sections reference; snapshot test guards the section list against going stale.

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
