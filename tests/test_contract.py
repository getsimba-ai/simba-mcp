"""API-surface contract test (issue #15).

Pins a snapshot of the Simba API v1 request parameters and asserts every one is
reachable through some MCP tool parameter — so tools can't silently trail the
API. When core adds a request parameter:

1. Add it to CONTRACT below (this is the reviewable act), pointing at the tool
   parameter that should carry it — the test now fails.
2. Expose it on the tool.

Parameters deliberately not exposed go in EXCLUDED_BY_DESIGN with a reason.

Snapshot source: the Simba public API v1 surface (ingest, results, models,
optimizer, scenario and project routes), reviewed 2026-08-26.
"""

import inspect

from simba_mcp import server

# endpoint -> {api_request_param: "tool_name.tool_param"}
CONTRACT = {
    "POST /api/v1/ingest": {
        "name": "upload_data.name",
        "filename": "upload_data.filename",
        "roles": "upload_data.roles",
    },
    "GET /api/v1/datasets/{id}/report": {
        "dataset_id": "get_data_report.dataset_id",
        "start": "get_data_report.start",
        "end": "get_data_report.end",
        "granularity": "get_data_report.granularity",
        "group_by": "get_data_report.group_by",
        "hierarchy": "get_data_report.hierarchy",
        "metrics": "get_data_report.metrics",
        "roles": "get_data_report.roles",
    },
    "GET /api/v1/ingest": {
        "limit": "list_uploads.limit",
        "offset": "list_uploads.offset",
        "name": "list_uploads.name",
    },
    "GET /api/v1/ingest/{id}": {
        "file_id": "get_upload.file_id",
    },
    "GET /api/v1/models": {
        "include_unsaved": "list_models.include_unsaved",
        "limit": "list_models.limit",
        "offset": "list_models.offset",
    },
    "POST /api/v1/models": {
        "data_source": "create_model.uploaded_file_id",
        "date_column": "create_model.date_column",
        "kpi_column": "create_model.kpi_column",
        "hierarchy_column": "create_model.hierarchy_column",
        "channels": "create_model.channels",
        "multiplier_column": "create_model.multiplier_column",
        "control_columns": "create_model.control_columns",
        "total_media_effect": "create_model.total_media_effect",
        "priors": "create_model.priors",
        "config.trend": "create_model.trend",
        "config.seasonality": "create_model.seasonality",
        "config.likelihood": "create_model.likelihood",
        "config.saturation_type": "create_model.saturation_type",
        "config.transform_order": "create_model.transform_order",
        "config.link": "create_model.link",
        "config.channel_groups": "create_model.channel_groups",
        "config.control_reference": "create_model.control_reference",
        "config.attribution": "create_model.attribution",
        "config.annual_discount_rate": "create_model.annual_discount_rate",
        "config.sampler": "create_model.sampler",
        "config.reporting_kernel": "create_model.reporting_kernel",
        "operating_margin": "create_model.operating_margin",
        "operating_margin_column": "create_model.operating_margin_column",
        "name": "create_model.name",
        "calibration": "create_model.calibration",
    },
    "GET /api/v1/models/{hash}": {
        "model_hash": "get_model.model_hash",
    },
    "DELETE /api/v1/models/{hash}": {
        "model_hash": "delete_model.model_hash",
    },
    "PATCH /api/v1/models/{hash}": {
        "name": "rename_model.name",
    },
    "POST /api/v1/models/{hash}/save": {
        "name": "save_model.name",
        "project_id": "save_model.project_id",
    },
    "POST /api/v1/models/{hash}/unsave": {
        "model_hash": "unsave_model.model_hash",
    },
    "GET /api/v1/projects": {
        # The endpoint takes no request parameters — pin reachability of the
        # tool itself via its context param.
        "(none)": "list_projects.ctx",
    },
    "POST /api/v1/projects": {
        "name": "create_project.name",
        "team_id": "create_project.team_id",
    },
    "PATCH /api/v1/projects/{id}": {
        "project_id": "rename_project.project_id",
        "name": "rename_project.name",
    },
    "POST /api/v1/models (model_type=var)": {
        "data_source": "create_var_model.uploaded_file_id",
        "date_column": "create_var_model.date_column",
        "config.endogenous_vars": "create_var_model.endogenous_vars",
        "config.exogenous_vars": "create_var_model.exogenous_vars",
        "config.lags": "create_var_model.lags",
        "config.forecast_horizon": "create_var_model.forecast_horizon",
        "config.base_variable": "create_var_model.base_variable",
        "config.equity_variables": "create_var_model.equity_variables",
        "config.lre_horizon": "create_var_model.lre_horizon",
        "config.lre_ci": "create_var_model.lre_ci",
        "config.var_priors": "create_var_model.var_priors",
        "name": "create_var_model.name",
    },
    "POST /api/v1/models/{hash}/link_var": {
        "var_model_hash": "link_var_model.var_model_hash",
        "channel_map": "link_var_model.channel_map",
    },
    "DELETE /api/v1/models/{hash}/link_var": {
        "model_hash": "unlink_var_model.model_hash",
    },
    "PUT /api/v1/models/{hash}/contribution-groups": {
        "contribution_groups": "set_contribution_groups.contribution_groups",
    },
    "GET /api/v1/models/{hash}/contribution-groups": {
        "model_hash": "get_contribution_groups.model_hash",
    },
    "GET /api/v1/models/{hash}/results": {
        "sections": "get_model_results.sections",
        "format": "get_model_results.format",
        "start": "get_model_results.start",
        "end": "get_model_results.end",
        "granularity": "get_model_results.granularity",
    },
    "POST /api/v1/models/{hash}/optimize": {
        "total_budget": "run_optimizer.total_budget",
        "num_periods": "run_optimizer.num_periods",
        "gamma": "run_optimizer.gamma",
        "currency": "run_optimizer.currency",
        "bounds": "run_optimizer.bounds",
        "laydown_weights": "run_optimizer.laydown_weights",
        "period_cpm": "run_optimizer.period_cpm",
        "objective": "run_optimizer.objective",
        "forward_margin": "run_optimizer.forward_margin",
        "period_multiplier": "run_optimizer.period_multiplier",
        "include_historical_effect": "run_optimizer.include_historical_effect",
        "enable_warm_start": "run_optimizer.enable_warm_start",
        "optimizer_engine": "run_optimizer.optimizer_engine",
        "sigma_penalty": "run_optimizer.sigma_penalty",
        "group_bounds": "run_optimizer.group_bounds",
    },
    "GET /api/v1/models/{hash}/optimize/runs": {
        "limit": "list_runs.limit",
        "offset": "list_runs.offset",
    },
    "GET /api/v1/models/{hash}/scenario/runs": {
        "limit": "list_runs.limit",
        "offset": "list_runs.offset",
    },
    "GET /api/v1/models/{hash}/optimize/runs/{run_id}": {
        "run_id": "get_optimizer_results.run_id",
    },
    "GET /api/v1/models/{hash}/scenario/runs/{run_id}": {
        "run_id": "get_scenario_results.run_id",
    },
    "PATCH /api/v1/models/{hash}/optimize/runs/{run_id}": {
        "name": "update_run.name",
        "notes": "update_run.notes",
        "tags": "update_run.tags",
    },
    "POST /api/v1/models/{hash}/optimize/runs/{run_id}/pin": {
        "pinned": "set_run_pinned.pinned",
    },
    "PATCH /api/v1/models/{hash}/scenario/runs/{run_id}": {
        "name": "update_run.name",
        "notes": "update_run.notes",
        "tags": "update_run.tags",
    },
    "POST /api/v1/models/{hash}/scenario/runs/{run_id}/pin": {
        "pinned": "set_run_pinned.pinned",
    },
    "POST /api/v1/models/{hash}/scenario/template": {
        "periods_forward": "get_scenario_template.periods_forward",
    },
    "POST /api/v1/models/{hash}/scenario": {
        "scenario_data": "run_scenario.scenario_data",
        "spend_metadata": "run_scenario.spend_metadata",
        "rebuild_model": "run_scenario.rebuild_model",
        "evaluate_holdout": "run_scenario.evaluate_holdout",
        "skip_slicing": "run_scenario.skip_slicing",
        "proxy_channels": "run_scenario.proxy_channels",
    },
    "POST /api/v1/pipelines/{ref}/runs": {
        "pipeline_ref": "run_pipeline.pipeline_ref",
        "start_date": "run_pipeline.start_date",
        "end_date": "run_pipeline.end_date",
    },
    "GET /api/v1/pipelines/{ref}/runs/{run_id}": {
        "pipeline_ref": "get_pipeline_run.pipeline_ref",
        "run_id": "get_pipeline_run.run_id",
    },
    "PUT /api/v1/pipelines/{ref}/schedule": {
        "pipeline_ref": "set_pipeline_schedule.pipeline_ref",
        "cadence": "set_pipeline_schedule.cadence",
        "hour_utc": "set_pipeline_schedule.hour_utc",
        "weekday": "set_pipeline_schedule.weekday",
        "enabled": "set_pipeline_schedule.enabled",
    },
    "GET /api/v1/campaigns": {
        "model": "list_campaigns.model_hash",
        "platform": "list_campaigns.platform",
        "unmapped_only": "list_campaigns.unmapped_only",
        "start": "list_campaigns.start",
        "end": "list_campaigns.end",
        "limit": "list_campaigns.limit",
        "cursor": "list_campaigns.cursor",
    },
    "GET /api/v1/campaigns/report": {
        "model": "get_campaign_report.model_hash",
        "start": "get_campaign_report.start",
        "end": "get_campaign_report.end",
        "granularity": "get_campaign_report.granularity",
        "group_by": "get_campaign_report.group_by",
        "platform": "get_campaign_report.platform",
        "channel": "get_campaign_report.channel",
        "campaign_id": "get_campaign_report.campaign_id",
        "metrics": "get_campaign_report.metrics",
    },
    "GET /api/v1/campaigns/incrementality": {
        "model": "get_campaign_incrementality.model_hash",
        "start": "get_campaign_incrementality.start",
        "end": "get_campaign_incrementality.end",
        "level": "get_campaign_incrementality.level",
    },
    "GET /api/v1/campaigns/marginal": {
        "model": "get_campaign_marginal_returns.model_hash",
        "start": "get_campaign_marginal_returns.start",
        "end": "get_campaign_marginal_returns.end",
        "level": "get_campaign_marginal_returns.level",
    },
    "POST /api/v1/campaigns/daily-budgets": {
        "model": "recommend_campaign_budgets.model_hash",
        "observation_window": "recommend_campaign_budgets.observation_window",
        "currency": "recommend_campaign_budgets.currency",
        "channel_daily_budgets": "recommend_campaign_budgets.channel_daily_budgets",
        "optimizer_run_id": "recommend_campaign_budgets.optimizer_run_id",
        "level": "recommend_campaign_budgets.level",
        "max_step_fraction": "recommend_campaign_budgets.max_step_fraction",
        "bounds": "recommend_campaign_budgets.bounds",
    },
    "PUT /api/v1/campaigns/map": {
        "model": "set_campaign_mapping.model_hash",
        "rows": "set_campaign_mapping.rows",
        "tolerance": "set_campaign_mapping.tolerance",
    },
    "GET /api/v1/projects/{id}/incrementality-tests": {
        "project_id": "list_incrementality_tests.project_id",
        "type": "list_incrementality_tests.type",
        "status": "list_incrementality_tests.status",
        "channel": "list_incrementality_tests.channel",
        "limit": "list_incrementality_tests.limit",
        "cursor": "list_incrementality_tests.cursor",
    },
    "POST /api/v1/projects/{id}/incrementality-tests": {
        "project_id": "create_incrementality_test.project_id",
        "record": "create_incrementality_test.record",
    },
    "POST /api/v1/projects/{id}/incrementality-tests/import": {
        "project_id": "import_incrementality_tests.project_id",
        "source": "import_incrementality_tests.source",
        "content": "import_incrementality_tests.content",
        "dry_run": "import_incrementality_tests.dry_run",
        "defaults": "import_incrementality_tests.defaults",
        "overrides": "import_incrementality_tests.overrides",
    },
    "GET /api/v1/incrementality-tests/{id}": {
        "test_id": "get_incrementality_test.test_id",
        "version": "get_incrementality_test.version",
    },
    "GET /api/v1/incrementality-tests/{id}/calibration": {
        "test_id": "get_incrementality_test.test_id",
        "model_hash": "get_incrementality_test.model_hash",
        "version": "get_incrementality_test.version",
        "channel": "get_incrementality_test.channel",
        "confirm_kpi": "get_incrementality_test.confirm_kpi",
    },
}

# api_param -> reason it is intentionally unreachable via MCP
EXCLUDED_BY_DESIGN = {
    "PUT /api/v1/campaigns/source": "Registering a pipeline as the campaign facts source binds "
    "data whose credentials the agent cannot see; a human registers it in the app.",
    "DELETE /api/v1/campaigns/source/{pipeline}": "See PUT /api/v1/campaigns/source.",
    "GET /api/v1/campaigns/source": "See PUT /api/v1/campaigns/source.",
    "GET /api/v1/campaigns/map": "set_campaign_mapping returns the same report, and "
    "list_campaigns carries each campaign's channel and suggestion.",
    "POST /api/v1/keys": "API-key management is session-auth only; an MCP tool "
    "holding one key must not mint or revoke keys.",
    "GET /api/v1/keys": "See POST /api/v1/keys.",
    "DELETE /api/v1/keys/{id}": "See POST /api/v1/keys.",
    # Deferred (tracked in issue #49) — accepted by the API but not yet
    # exposed; each needs its semantics documented before agents get it:
    "POST /api/v1/models config.sample_prior": "Deferred: prior-predictive "
    "mode (#395) returns a different artifact class than a fitted model; "
    "needs its own workflow docs before exposure (issue #49).",
    "POST /api/v1/models config.base_share_prior": "Deferred: elicited "
    "base-share prior (#442) is a strictly-validated nested object with "
    "elicitation semantics to document first (issue #49).",
    "POST /api/v1/models/{hash}/scenario scenario_space": "Deferred: raw- "
    "vs model-space flag (#573) silently changes how scenario rows are "
    "transformed — semantics-changing, document before exposing (issue #49).",
    "POST /api/v1/models/{hash}/scenario periodicity": "Deferred: scenario "
    "periodicity override; document interaction with the model's own "
    "periodicity first (issue #49).",
    "PATCH /api/v1/incrementality-tests/{id}": "Deferred: editing a recorded "
    "test replaces a shared, versioned record other models may cite; add when "
    "an agent needs it (issue #34).",
    "GET /api/v1/incrementality-tests/{id}/versions": "Deferred with PATCH: the "
    "version list matters once agents can edit (issue #34).",
    "DELETE /api/v1/incrementality-tests/{id}": "Deferred: retiring removes a "
    "test from every project member's list; add when an agent needs it (issue #34).",
    "POST /api/v1/incrementality-tests/preview": "The web wizard's preview for an "
    "unsaved model; agents derive through get_incrementality_test(model_hash=...) "
    "or create_model(calibration=...).",
}


def _tool_params(tool_name: str) -> set[str]:
    fn = getattr(server, tool_name)
    return set(inspect.signature(fn).parameters)


class TestContract:
    def test_every_contract_param_reachable(self):
        missing = []
        for endpoint, mapping in CONTRACT.items():
            for api_param, target in mapping.items():
                tool_name, _, tool_param = target.partition(".")
                if tool_param not in _tool_params(tool_name):
                    missing.append(f"{endpoint} param {api_param!r} -> {target}")
        assert not missing, (
            "API v1 request parameters unreachable through MCP tools:\n  " + "\n  ".join(missing)
        )

    def test_contract_tools_exist(self):
        for mapping in CONTRACT.values():
            for target in mapping.values():
                tool_name = target.partition(".")[0]
                assert hasattr(server, tool_name), f"unknown tool {tool_name!r}"

    def test_exclusions_have_reasons(self):
        for endpoint, reason in EXCLUDED_BY_DESIGN.items():
            assert len(reason) > 10, f"exclusion {endpoint!r} needs a real reason"
