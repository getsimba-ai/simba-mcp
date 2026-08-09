# Changelog

All notable changes to the SIMBA MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## Unreleased

### Added

- `create_model` exposes the API's model-architecture options: `saturation_type` ("tanh"/"michaelis_menten"/"negative_exponential"/"generalized_log"), `transform_order` ("adstock_first"/"saturation_first"), and `link` ("identity" = additive, "log" = multiplicative Model Form). Defaults omit the keys, so existing payloads are byte-identical. Multiplicative, saturate-then-carry models are now reachable through MCP.
- `create_model` priors docstring documents the adstock/saturation prior-override fields the API already accepts: `half_life_lower`/`half_life_upper` (preferred over legacy decay bounds), `theta_mean`/`theta_sd` (delayed adstock), `dual_weight_mean`/`dual_weight_sd` (dual_geometric), `sat_shape_mean`/`sat_shape_sd` (generalized_log). These passed through before but were undiscoverable.
- `get_model_results` documents three previously undocumented sections — `posterior` (per-variable mean/sd/94% HDI/r_hat), `financials` (operating margin), `model_config` (resolved model specification) — plus the `Overlap` contribution column emitted by multiplicative models (negative shared-synergy reconciliation term; never a channel) and the `generalized_log` saturation family.
- `create_model` exposes `channel_groups` (adstock groups): named groups of channels that tie their carryover parameters — and optionally saturation — to one shared value (e.g. shared "Long"/"Short" carryover classes). Serialized only when non-empty. Requires an API with `config.channel_groups` support.
- Contract snapshot now pins `config.saturation_type`, `config.transform_order`, `config.link`, and `config.channel_groups` (snapshot re-reviewed against core `src/api/v1` as of 2026-08-09).

- `run_optimizer` now exposes the API's remaining optimizer options: `objective` ("revenue"/"profit"), `forward_margin`, `period_multiplier`, `include_historical_effect`, `enable_warm_start`. Profit optimization is now reachable through MCP; omitting the new params produces byte-identical payloads to 0.1.2 (issue #11).
- `upload_data` accepts `csv_path` (mutually exclusive with `csv_content`): the server reads the file directly, so large CSVs no longer transit the LLM conversation. Pre-flight existence/size checks; dataset name defaults to the file stem. Local (stdio) servers only — disabled on HTTP/SSE transports unless `SIMBA_MCP_ALLOW_LOCAL_FILES=1` (issue #14).
- `get_model_results` gains context-size controls for LLM use (issue #13): `format="csv"` (returns `{"format": "csv", "content": ...}`; the client now handles non-JSON responses instead of raising), `channels=[...]` client-side filtering (curve sections, decay_curves, saturation, channel_summary, coefficients, mroi_summary; name matching tolerates case/spaces and the `_activity`/`_spend` suffix), and `max_grid_points` downsampling of the 100-point curves (endpoints preserved). `contributions` is never filtered — its control columns are indistinguishable from channels client-side. Defaults unchanged.
- Parameter-completeness sweep vs API v1 (issue #15): `list_models` exposes `offset` (paging); `run_scenario` exposes `evaluate_holdout`, `skip_slicing`, `proxy_channels` (serialized only when non-default — existing payloads unchanged); `upload_data` exposes `filename`; `get_scenario_template` docstring documents the `operating_margin`, `variable_transforms`, and `variable_classification` response fields.
- Contract test (`tests/test_contract.py`) pinning the v1 request-parameter surface: it fails when a snapshot parameter isn't reachable through any MCP tool, with an `EXCLUDED_BY_DESIGN` list for the deliberate exclusions (API-key management). README documents that exclusion.

### Fixed

- `create_model` likelihood docs listed `"negbinomial"`, which the API rejects — corrected to the canonical values: `normal`, `lognormal`, `logit`, `studentt`, `poisson`, `negativebinomial`, `quantile`.
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
