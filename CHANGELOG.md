# Changelog

All notable changes to the SIMBA MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## Unreleased

### Added

- `run_optimizer` now exposes the API's remaining optimizer options: `objective` ("revenue"/"profit"), `forward_margin`, `period_multiplier`, `include_historical_effect`, `enable_warm_start`. Profit optimization is now reachable through MCP; omitting the new params produces byte-identical payloads to 0.1.2 (issue #11).
- `upload_data` accepts `csv_path` (mutually exclusive with `csv_content`): the server reads the file directly, so large CSVs no longer transit the LLM conversation. Pre-flight existence/size checks; dataset name defaults to the file stem. Local (stdio) servers only — disabled on HTTP/SSE transports unless `SIMBA_MCP_ALLOW_LOCAL_FILES=1` (issue #14).
- `get_model_results` gains context-size controls for LLM use (issue #13): `format="csv"` (returns `{"format": "csv", "content": ...}`; the client now handles non-JSON responses instead of raising), `channels=[...]` client-side filtering (curve sections, decay_curves, saturation, channel_summary, coefficients, mroi_summary; name matching tolerates case/spaces and the `_activity`/`_spend` suffix), and `max_grid_points` downsampling of the 100-point curves (endpoints preserved). `contributions` is never filtered — its control columns are indistinguishable from channels client-side. Defaults unchanged.
- Parameter-completeness sweep vs API v1 (issue #15): `list_models` exposes `offset` (paging); `run_scenario` exposes `evaluate_holdout`, `skip_slicing`, `proxy_channels` (serialized only when non-default — existing payloads unchanged); `upload_data` exposes `filename`; `get_scenario_template` docstring documents the `operating_margin`, `variable_transforms`, and `variable_classification` response fields.
- Contract test (`tests/test_contract.py`) pinning the v1 request-parameter surface: it fails when a snapshot parameter isn't reachable through any MCP tool, with an `EXCLUDED_BY_DESIGN` list for the deliberate exclusions (API-key management). README documents that exclusion.

### Fixed

- `get_model_results` docstring now documents all 14 API sections — previously `saturation`, `mroi_summary`, and `long_run_rollup` were undiscoverable — with per-section semantics (issue #12).
- `contributions` vs `coefficients` clarified: contributions are KPI/unit space (multiplier not applied); `coefficients` is the per-period per-channel revenue table.
- Channel-naming rule stated precisely in `get_model_results`, `run_optimizer`, and `run_scenario`: results/template keys are the channel's activity-column name, not `channels[].name`; plus a note that record dates are millisecond epoch integers.
- README: updated the channel-names gotcha and added a Results sections reference; snapshot test guards the section list against going stale.
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
