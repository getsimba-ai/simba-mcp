"""API-surface contract test (issue #15).

Pins a snapshot of the Simba API v1 request parameters and asserts every one is
reachable through some MCP tool parameter — so tools can't silently trail the
API. When core adds a request parameter:

1. Add it to CONTRACT below (this is the reviewable act), pointing at the tool
   parameter that should carry it — the test now fails.
2. Expose it on the tool.

Parameters deliberately not exposed go in EXCLUDED_BY_DESIGN with a reason.

Snapshot source: simba core repo `src/api/v1/*.py` (ingest.py, results.py,
models.py, optimizer.py, scenario.py), reviewed 2026-08-09.
"""

import inspect

from simba_mcp import server

# endpoint -> {api_request_param: "tool_name.tool_param"}
CONTRACT = {
    "POST /api/v1/ingest": {
        "name": "upload_data.name",
        "filename": "upload_data.filename",
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
    },
    "GET /api/v1/models/{hash}/results": {
        "sections": "get_model_results.sections",
        "format": "get_model_results.format",
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
    },
    "GET /api/v1/models/{hash}/optimize/runs/{run_id}": {
        "run_id": "get_optimizer_results.run_id",
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
}

# api_param -> reason it is intentionally unreachable via MCP
EXCLUDED_BY_DESIGN = {
    "POST /api/v1/keys": "API-key management is session-auth only; an MCP tool "
    "holding one key must not mint or revoke keys.",
    "GET /api/v1/keys": "See POST /api/v1/keys.",
    "DELETE /api/v1/keys/{id}": "See POST /api/v1/keys.",
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
