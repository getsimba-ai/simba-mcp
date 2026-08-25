# Changelog

All notable changes to the SIMBA MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## Unreleased

### Fixed

- `run_optimizer` gamma docstring no longer inverts the semantics (issue #31): gamma is an uncertainty-aversion weight — 0 maximizes expected return (most aggressive), higher values penalize uncertainty (more conservative). The old text called 0 "conservative" and 1 "aggressive", contradicting both the objective (`mean − gamma·spread`) and its own next line. Also notes the dashboard's typical 0–0.1 range, and tags `alpha_sd`/`scalars`/`decay_lower`/`decay_upper` as legacy in `create_model`'s flat prior-field list.
- The `Overlap` emission gate is stated correctly in both docstrings that carry it (issue #32): Overlap requires `link="log"` AND `attribution="removal_lift"` (the API default). The 0.1.2 text claimed all multiplicative models add it and that absence means additive/pre-feature — false for aumann_shapley/shapley/proportional_normalized (the dashboard default), which allocate the interaction and close exactly without an Overlap column. A docstring guard test pins the corrected gate.
- `get_model_results` documents the four remaining undocumented sections (issue #27): `posterior_transforms` (importable transform-parameter posterior grid, keyed by activity column), `r_hat` (per-parameter R-hat over all posterior RVs, transform RVs included), `channel_map` (canonical name ↔ activity/spend column mapping — the join key), and `cohort_ledger` (per-(channel, source-period) forward-allocation ledger with PV-discounted financials; `{available: false}` on pre-artifact models). All four re-verified against the live results route. Also documents that `financials.operating_margin_series` is a date-string-keyed dict, not a list. The section-list guard test now pins all 22 sections.
- README API host regression fixed (issue #25): all five example sites read `app.simba-mmm.com`, which does not serve the API (verified live: connection failure, while `demo.simba-mmm.com` answers). Swept back to `demo.simba-mmm.com` — the same regression 0.1.1 fixed — and a test now fails if a stale host reappears in the README.

## 0.1.2 — 2026-08-25

### Added

- `get_model_results` documents the `*_mean` keys the `mroi_summary` section carries on post-#629 fits (`mroi_mean`, `mroi_profit_mean`, `pv_kernel_mass_mean`, and the `allperiods_unweighted` / `spendweighted_active` variants). The median is the displayed headline; the mean is the statistic that reconciles with the marginal-revenue curve, because derivative and mean commute and the median has no such identity. Agents must feature-detect: there is no backfill, so the keys are absent on anything fitted earlier, and a mean cannot be recovered from a stored median and HDI. Documentation only — no tool surface, request parameter, or filtering behaviour changes.

- Model curation (#575): `create_model` gains `name` (honoured verbatim by the API; omitted → generated `API_MMM_*` fallback, payload byte-identical), plus new tools `rename_model` (PATCH `/models/{hash}`) and `save_model` (POST `/models/{hash}/save` — files the model into a project so it appears in the default `list_models` listing and the dashboard's Saved Models; same saved-models cap as the dashboard, `error_type: "saved_limit"` at the cap). Contract snapshot pins all three surfaces.
- Saved-run curation (#576): `update_run` (PATCH rename/notes/tags — flips `auto_named` false permanently) and `set_run_pinned` (declarative, idempotent pin) over both artifacts (`optimizer` → `/optimize/runs/{run_id}`, `scenario` → `/scenario/runs/{run_id}`). Write scopes mirror creation: `optimize` / `scenario`. Contract snapshot pins the four route surfaces.
- `run_optimizer` exposes `group_bounds` (#570): joint budget constraints over channel sets in % of total budget, disjoint and feasibility-validated server-side; presence forces the slsqp engine and results gain `GroupBounds`/`GroupBoundsReport` columns. Contract snapshot pins the key.
- Long-term (VAR) models are now reachable through MCP (#569): `create_var_model` (endogenous/exogenous series, lags, forecast horizon, long-run-effects base/equity/horizon/ci, `var_priors`), plus `link_var_model`/`unlink_var_model` to attach a VAR to an MMM so `get_model_results` serves the `long_run_rollup` section. Contract snapshot pins all VAR request parameters.
- `set_contribution_groups`/`get_contribution_groups` (#436): persist the dashboard contributions-view driver groupings (colors, per-driver base adjustments, the `_channel_color_overrides` pseudo-group) next to the model via the new v1 route pair — with the explicit warning that this is NOT `create_model`'s adstock `channel_groups`. Contract snapshot pins the payload.

- `get_optimizer_results` accepts optional `run_id` (issue #33): with it, the tool fetches that specific optimization run via `GET /optimize/runs/{run_id}` — immune to later runs overwriting the model-level state, so pollers can reliably observe their own run's completion. Without it, behavior is unchanged (model-level latest). The docstring now documents the actual result surface and, critically, that the decision-math columns (`Revenue`/`ROI`, removal-lift counterfactual; `ObjectiveMarginal`) and the fitted-convention comparison columns (`OptimizedEvalRevenue`/`ROI`, `HistoricalRevenue`/`ROI`; `MroiAtOptimized` + 94% HDI bounds) answer different questions and must not be treated as interchangeable. Contract snapshot pins `run_id`.

- `create_model` exposes `control_reference` (#452, issue #28): per-control attribution reference points for multiplicative (`link="log"`) models — `{"control": "auto" | "absent" | "average" | "lowest" | "highest", "_default": ...}`, forwarded verbatim into `config.control_reference` on the same pattern as `channel_groups` (omitted when empty, so existing payloads are byte-identical). Fixes MCP-built multiplicative models silently getting unbounded control contributions (−157% of outcome) and a negative Base when a control never approaches zero. `get_model_results` documents the fit-time resolution reported back in `model_config.control_references` and the referenced control columns in `contributions`. Contract snapshot pins `config.control_reference`.

- `create_model` exposes the API's model-architecture options: `saturation_type` ("tanh"/"michaelis_menten"/"negative_exponential"/"generalized_log"), `transform_order` ("adstock_first"/"saturation_first"), and `link` ("identity" = additive, "log" = multiplicative Model Form). Defaults omit the keys, so existing payloads are byte-identical. Multiplicative, saturate-then-carry models are now reachable through MCP.
- `create_model` priors docstring documents the adstock/saturation prior-override fields the API already accepts: `half_life_lower`/`half_life_upper` (preferred over legacy decay bounds), `theta_mean`/`theta_sd` (delayed adstock), `dual_weight_mean`/`dual_weight_sd` (dual_geometric), `sat_shape_mean`/`sat_shape_sd` (generalized_log). These passed through before but were undiscoverable.
- `get_model_results` documents three previously undocumented sections — `posterior` (per-variable mean/sd/94% HDI/r_hat), `financials` (operating margin), `model_config` (resolved model specification) — plus the `Overlap` contribution column emitted by multiplicative models (negative shared-synergy reconciliation term; never a channel) and the `generalized_log` saturation family.
- `create_model` exposes `channel_groups` (adstock groups): named groups of channels that tie their carryover parameters — and optionally saturation — to one shared value (e.g. shared "Long"/"Short" carryover classes). Serialized only when non-empty. Requires an API with `config.channel_groups` support.
- Contract snapshot now pins `config.saturation_type`, `config.transform_order`, `config.link`, and `config.channel_groups` (snapshot re-reviewed against core `src/api/v1` as of 2026-08-09).

- `run_optimizer` now exposes the API's remaining optimizer options: `objective` ("revenue"/"profit"), `forward_margin`, `period_multiplier`, `include_historical_effect`, `enable_warm_start`. Profit optimization is now reachable through MCP; omitting the new params produces byte-identical payloads to 0.1.1 (issue #11).
- `upload_data` accepts `csv_path` (mutually exclusive with `csv_content`): the server reads the file directly, so large CSVs no longer transit the LLM conversation. Pre-flight existence/size checks; dataset name defaults to the file stem. Local (stdio) servers only — disabled on HTTP/SSE transports unless `SIMBA_MCP_ALLOW_LOCAL_FILES=1` (issue #14).
- `get_model_results` gains context-size controls for LLM use (issue #13): `format="csv"` (returns `{"format": "csv", "content": ...}`; the client now handles non-JSON responses instead of raising), `channels=[...]` client-side filtering (curve sections, decay_curves, saturation, channel_summary, coefficients, mroi_summary; name matching tolerates case/spaces and the `_activity`/`_spend` suffix), and `max_grid_points` downsampling of the 100-point curves (endpoints preserved). `contributions` is never filtered — its control columns are indistinguishable from channels client-side. Defaults unchanged.
- Parameter-completeness sweep vs API v1 (issue #15): `list_models` exposes `offset` (paging); `run_scenario` exposes `evaluate_holdout`, `skip_slicing`, `proxy_channels` (serialized only when non-default — existing payloads unchanged); `upload_data` exposes `filename`; `get_scenario_template` docstring documents the `operating_margin`, `variable_transforms`, and `variable_classification` response fields.
- Contract test (`tests/test_contract.py`) pinning the v1 request-parameter surface: it fails when a snapshot parameter isn't reachable through any MCP tool, with an `EXCLUDED_BY_DESIGN` list for the deliberate exclusions (API-key management). README documents that exclusion.
- Enriched MCP tool descriptions with inline gotchas (channel name matching, array requirements, NaN cleaning, async polling patterns) so AI agents get tips automatically.
- README: Gotchas & Tips section covering the 6 most common pitfalls.
- README: Common Errors table with causes and fixes.
- README: Direct API Access section with MCP vs API comparison, Python and curl quick-start examples.

### Fixed

- The MCP initialize handshake now reports simba-mcp's own package version instead of the mcp SDK's (issue #41). FastMCP 1.x accepts no version kwarg, and the low-level server falls back to `importlib.metadata.version("mcp")` when its version is unset — so clients saw the SDK version (e.g. `1.27.0`) as the server's.
- `create_model` likelihood docs listed `"negbinomial"`, which the API rejects — corrected to the canonical values: `normal`, `lognormal`, `logit`, `studentt`, `poisson`, `negativebinomial`, `quantile`.
- `get_model_results` docstring now documents all 14 API sections — previously `saturation`, `mroi_summary`, and `long_run_rollup` were undiscoverable — with per-section semantics (issue #12).
- `contributions` vs `coefficients` clarified: contributions are KPI/unit space (multiplier not applied); `coefficients` is the per-period per-channel revenue table.
- Channel-naming rule stated precisely in `get_model_results`, `run_optimizer`, and `run_scenario`: results/template keys are the channel's activity-column name, not `channels[].name`; plus a note that record dates are millisecond epoch integers.
- README: updated the channel-names gotcha and added a Results sections reference; snapshot test guards the section list against going stale.
- Upload size limit corrected: the API enforces **10 MB**, not the previously documented 50 MB. Docstring and README updated; oversized `csv_path` uploads fail fast with a clear message (issue #14).
- Row-minimum guidance no longer hardcodes "52 rows" — it defers to `get_data_schema` → `x-simba-constraints.min_rows` and notes that the upload response's `warnings` field is authoritative (issue #14).

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
