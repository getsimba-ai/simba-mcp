"""Current role examples: public synthetic contracts, separate from frozen paid trials."""

from dataclasses import dataclass

from .contracts import Case, Exchange, Step


@dataclass(frozen=True)
class RoleWorkflow:
    case: Case
    roles: tuple[str, ...]
    topic: str
    section: str
    intent: str
    preconditions: str
    limits: str


def role_workflows() -> list[RoleWorkflow]:
    """Complete jobs executed by the existing strict runner, never a second runner."""
    both = ("marketer", "reviewer", "data_scientist", "full")
    model = {"model_hash": "model-example"}
    window = {"start": "2026-09-01", "end": "2026-09-28"}

    def step(tool, args, method, path, response, *, query=None, body=None, status=200, fault=None):
        return Step(
            tool=tool,
            arguments=args,
            exchanges=[
                Exchange(
                    method=method,
                    path="/api/v1" + path,
                    query=query or {},
                    body=body,
                    response=response,
                    status=status,
                    fault=fault,
                )
            ],
            expected=response if status < 400 and not fault else {"_status_code": status},
            is_error=status >= 400 or fault is not None,
        )

    def workflow(id, roles, topic, section, intent, preconditions, limits, steps):
        return RoleWorkflow(
            Case(id=id, purpose=intent, steps=steps),
            roles,
            topic,
            section,
            intent,
            preconditions,
            limits,
        )

    upload = {
        "id": 7,
        "filename": "synthetic.csv",
        "source_type": "pipeline",
        "columns": [
            {"name": "date", "dtype": "date"},
            {"name": "units", "dtype": "number"},
            {"name": "search_spend", "dtype": "number"},
        ],
    }
    report = {
        "dataset": {"id": 7, "source": "pipeline", "sha256": "synthetic-digest"},
        "granularity": "month",
        "rows": [
            {
                "period_start": "2026-09-01",
                "period_end": "2026-09-30",
                "group": "all",
                "metric": "kpi",
                "value": 400,
                "unit": "units",
            },
            {
                "period_start": "2026-09-01",
                "period_end": "2026-09-30",
                "group": "all",
                "metric": "spend",
                "value": 1200,
                "unit": "GBP",
            },
        ],
        "meta": {"basis": "dataset", "aggregation": {"kpi": "sum", "spend": "sum"}},
    }
    data_args = {
        "dataset_id": 7,
        **window,
        "granularity": "month",
        "metrics": ["kpi", "spend"],
        "roles": {"units": "kpi"},
    }
    data_query = {
        **window,
        "granularity": "month",
        "metrics": "kpi,spend",
        "roles": '{"units": "kpi"}',
    }
    campaign = {
        "platform": "meta",
        "account_id": "account-example",
        "campaign_id": "campaign-example",
        "channel": "search_clicks",
        "status": "mapped",
    }
    campaign_list = {"campaigns": [campaign], "currency": "GBP", "window": window}
    marginal = {
        "context_key": "basis-example",
        "currency": "GBP",
        "minor_digits": 2,
        "channels": [{"channel": "search_clicks", "status": "ready"}],
        "rows": [
            {
                **campaign,
                "current_daily_spend": 100,
                "marginal_return": 1.4,
                "interval_status": "unavailable",
            }
        ],
        "provenance": {"curve_revision": "curve-example", "map_version": 3},
    }
    budget_args = {
        **model,
        "observation_window": window,
        "currency": "GBP",
        "channel_daily_budgets": {"search_clicks": 100},
        "expected_context_key": "basis-example",
    }
    budget_body = {
        "model": "model-example",
        "observation_window": window,
        "currency": "GBP",
        "channel_daily_budgets": {"search_clicks": 100},
        "level": "campaign",
        "max_step_fraction": 0.2,
        "expected_context_key": "basis-example",
    }

    def marginal_step(response=marginal):
        return step(
            "get_campaign_marginal_returns",
            {**model, **window},
            "GET",
            "/campaigns/marginal",
            response,
            query={"model": "model-example", **window, "level": "campaign"},
        )

    rows = [{"platform": "meta", "campaign_id": "campaign-example", "channel": "search_clicks"}]
    mapping_args = {**model, "rows": rows}
    mapping_body = {"rows": rows, "tolerance": 0.05}
    mapping_query = {"model": "model-example"}
    mapping_limits = (
        "Explicit user intent is required. PUT replaces the whole map; retain all authorised rows. "
        "A timeout leaves the write uncertain. Inspect facts, then hand off before another write."
    )
    suite = [
        workflow(
            "role_actual_data",
            both,
            "reporting",
            "workflow",
            "Find an existing dataset and report September actual KPI and spend.",
            "An owned dataset exists; the user declares units as KPI. No upload or pipeline refresh.",
            "Preserve dataset identity, declared roles, units and aggregation. Actual totals are not model attribution.",
            [
                step(
                    "list_uploads",
                    {"limit": 10},
                    "GET",
                    "/ingest",
                    {"files": [{"id": 7, "filename": "synthetic.csv"}], "count": 1},
                    query={"limit": "10", "offset": "0"},
                ),
                step("get_upload", {"file_id": 7}, "GET", "/ingest/7", upload),
                step(
                    "get_data_schema",
                    {},
                    "GET",
                    "/ingest/schema",
                    {"x-simba-roles": {"kpi": {"aggregation": "sum"}}},
                ),
                step(
                    "get_data_report",
                    data_args,
                    "GET",
                    "/datasets/7/report",
                    report,
                    query=data_query,
                ),
            ],
        ),
        workflow(
            "role_report_recovery",
            both,
            "reporting",
            "workflow",
            "Recover an oversized report by narrowing it, without changing the data.",
            "Dataset 7 is known; declared roles are retained.",
            "Do not truncate results or upload, refresh or fit to repair a reporting refusal.",
            [
                step(
                    "get_data_report",
                    {"dataset_id": 7},
                    "GET",
                    "/datasets/7/report",
                    {"code": "report_too_large"},
                    query={"granularity": "native"},
                    status=413,
                ),
                step(
                    "get_data_report",
                    data_args,
                    "GET",
                    "/datasets/7/report",
                    report,
                    query=data_query,
                ),
            ],
        ),
        workflow(
            "role_campaign_facts",
            both,
            "campaigns",
            "workflow",
            "Inspect campaign spend beside platform-attributed and channel-derived incremental evidence.",
            "Model and campaign-facts source exist; facts and attribution windows match.",
            "Platform conversions are attributed facts. Campaign incremental ROAS inherits channel assumptions and is not independently measured.",
            [
                step(
                    "list_campaigns", model, "GET", "/campaigns", campaign_list, query=mapping_query
                ),
                step(
                    "get_campaign_report",
                    {**model, **window, "group_by": "channel", "metrics": ["spend"]},
                    "GET",
                    "/campaigns/report",
                    {
                        "rows": [
                            {
                                "group": "search_clicks",
                                "metric": "spend",
                                "value": 2800,
                                "unit": "GBP",
                            }
                        ],
                        "meta": {"basis": "campaign_facts"},
                    },
                    query={
                        "model": "model-example",
                        **window,
                        "granularity": "native",
                        "group_by": "channel",
                        "metrics": "spend",
                    },
                ),
                step(
                    "get_campaign_incrementality",
                    {**model, **window},
                    "GET",
                    "/campaigns/incrementality",
                    {
                        "rows": [
                            {
                                **campaign,
                                "incremental_roas": 2.0,
                                "method": "channel_factor",
                                "interval": "unavailable",
                            }
                        ]
                    },
                    query={"model": "model-example", **window, "level": "campaign"},
                ),
            ],
        ),
        workflow(
            "role_campaign_empty",
            both,
            "campaigns",
            "workflow",
            "Stop and hand off when campaign facts are unavailable.",
            "A model is known; the app owns source registration.",
            "Missing facts are not zero conversions. Do not create or run a pipeline.",
            [
                step(
                    "get_campaign_report",
                    model,
                    "GET",
                    "/campaigns/report",
                    {"code": "campaign_facts_empty"},
                    query={"model": "model-example", "granularity": "native"},
                    status=404,
                )
            ],
        ),
        workflow(
            "role_campaign_mapping",
            ("marketer", "data_scientist", "full"),
            "campaigns",
            "mapping",
            "Replace the explicitly authorised complete campaign map, then inspect the result.",
            "The user approves all replacement rows and exact channel keys.",
            mapping_limits,
            [
                step(
                    "set_campaign_mapping",
                    mapping_args,
                    "PUT",
                    "/campaigns/map",
                    {"map": rows, "conflicts": [], "drift": []},
                    body=mapping_body,
                    query=mapping_query,
                ),
                step(
                    "list_campaigns", model, "GET", "/campaigns", campaign_list, query=mapping_query
                ),
            ],
        ),
        workflow(
            "role_mapping_uncertain",
            ("marketer", "data_scientist", "full"),
            "campaigns",
            "mapping",
            "Inspect campaign facts after an uncertain mapping write; never replay automatically.",
            "One replacement was authorised; its transport fails.",
            mapping_limits,
            [
                step(
                    "set_campaign_mapping",
                    mapping_args,
                    "PUT",
                    "/campaigns/map",
                    {},
                    body=mapping_body,
                    query=mapping_query,
                    status=503,
                    fault="timeout",
                ),
                step(
                    "list_campaigns", model, "GET", "/campaigns", campaign_list, query=mapping_query
                ),
            ],
        ),
        workflow(
            "role_campaign_budget",
            both,
            "campaigns",
            "budgets",
            "Inspect marginal evidence and calculate a bounded daily-equivalent campaign allocation.",
            "Completed model, matching currency, facts and curves; an explicit daily channel total is supplied.",
            "Read-only POST creates no run or platform change. Keep composite identity, provenance, constraints and unavailable uncertainty.",
            [
                marginal_step(),
                step(
                    "recommend_campaign_budgets",
                    budget_args,
                    "POST",
                    "/campaigns/daily-budgets",
                    {
                        "currency": "GBP",
                        "channels": [
                            {
                                "channel": "search_clicks",
                                "status": "ready",
                                "total_daily_budget": 100,
                                "rows": [
                                    {
                                        **campaign,
                                        "recommended_daily_budget": 100,
                                        "interval_status": "unavailable",
                                    }
                                ],
                            }
                        ],
                    },
                    body=budget_body,
                ),
            ],
        ),
        workflow(
            "role_budget_stale",
            both,
            "campaigns",
            "budgets",
            "Inspect fresh evidence after a stale campaign-budget basis refuses calculation.",
            "The reviewed context key is supplied; facts change before calculation.",
            "Do not relax constraints, retry the POST or apply budgets automatically.",
            [
                marginal_step(),
                step(
                    "recommend_campaign_budgets",
                    budget_args,
                    "POST",
                    "/campaigns/daily-budgets",
                    {"code": "stale_context"},
                    body=budget_body,
                    status=409,
                ),
                marginal_step({**marginal, "context_key": "basis-new"}),
            ],
        ),
        workflow(
            "role_experiment_priorities",
            both,
            "campaigns",
            "experiments",
            "Read experiment screening priorities and retain exclusions and uncertainty limits.",
            "A saved model has posterior marginal evidence and the backend supports test-priorities.",
            "Score is local binary perfect-information screening, not expected test benefit, design or recommended test budget.",
            [
                step(
                    "recommend_incrementality_tests",
                    {**model, "budget": 1000.0, "limit": 3},
                    "GET",
                    "/models/model-example/test-priorities",
                    {
                        "method": "normal_approximation",
                        "budget": 1000.0,
                        "items": [
                            {
                                "channel": "search_clicks",
                                "score": 12.0,
                                "design_hint": {"available": False},
                            }
                        ],
                        "excluded": [{"channel": "tv_grps", "reason": "posterior_unavailable"}],
                    },
                    query={"budget": "1000.0", "hurdle": "1.0", "limit": "3"},
                )
            ],
        ),
        workflow(
            "role_experiment_unsupported",
            both,
            "campaigns",
            "experiments",
            "Stop experiment screening when the backend endpoint is unsupported.",
            "Saved model is known; no experiment creation is authorised.",
            "A missing route is an unavailable capability. Preserve refusal and hand off; do not fit or fabricate a score.",
            [
                step(
                    "recommend_incrementality_tests",
                    model,
                    "GET",
                    "/models/model-example/test-priorities",
                    {"code": "unsupported_operation"},
                    query={"hurdle": "1.0", "limit": "5"},
                    status=405,
                )
            ],
        ),
        workflow(
            "role_native_results",
            both,
            "results",
            "visuals",
            "Read response curves and decomposition in a visual or JSON-only client.",
            "Saved model is known. No capability/schema discovery is needed.",
            "JSON remains authoritative. Missing points stay gaps; Overlap is a separate reconciliation term in KPI units.",
            [
                step(
                    "show_response_curves",
                    model,
                    "GET",
                    "/models/model-example/results",
                    {
                        "response_curves": [{"Spend": 100, "search_clicks": None}],
                        "channel_map": {"search_clicks": "Search"},
                    },
                    query={
                        "format": "json",
                        "sections": "response_curves,mroi_summary,channel_map,model_config",
                    },
                ),
                step(
                    "show_decomposition",
                    model,
                    "GET",
                    "/models/model-example/results",
                    {
                        "contributions": [
                            {"Date": "2026-09-01", "search_clicks": 10, "Overlap": -2}
                        ],
                        "model_config": {"attribution": "removal_lift"},
                    },
                    query={"format": "json", "sections": "contributions,channel_map,model_config"},
                ),
            ],
        ),
        workflow(
            "role_saved_allocation",
            both,
            "optimiser",
            "saved",
            "Compare two exact saved optimiser allocations without creating a new run.",
            "Two owned saved run IDs are supplied for the same model.",
            "Decision Revenue/ROI and OptimizedEvalRevenue/ROI remain separate; read-only views create no allocation.",
            [
                step(
                    "show_optimizer_allocation",
                    {**model, "run_id": run_id},
                    "GET",
                    f"/models/model-example/optimize/runs/{run_id}",
                    {
                        "run_id": run_id,
                        "model_hash": "model-example",
                        "status": "complete",
                        "results": [
                            {
                                "Channel": "search_clicks",
                                "Spend": spend,
                                "Revenue": 2 * spend,
                                "ROI": 2.0,
                                "OptimizedEvalRevenue": 3 * spend,
                                "OptimizedEvalROI": 3.0,
                            }
                        ],
                    },
                )
                for run_id, spend in (("optim-one", 100), ("optim-two", 120))
            ],
        ),
    ]
    # Retain existing representative authoring and missing-evidence contracts.
    from .cases import cases

    baseline = {case.id: case for case in cases()}
    suite.extend(
        [
            RoleWorkflow(
                baseline["study_review"],
                both,
                "studies",
                "review",
                "Review saved Studies evidence without calling missing holdout evidence a pass.",
                "Saved study and evaluations are known.",
                "not_evaluated stays not_evaluated. A read may produce an access audit event.",
            ),
            RoleWorkflow(
                baseline["create_mmm"],
                ("data_scientist", "full"),
                "mmm",
                "building",
                "Create one explicitly authorised synthetic MMM and inspect status.",
                "Dataset/schema prerequisites and user fit budget are supplied; fixture performs no real fit.",
                "Marketer/reviewer must stop and reconnect with full before authoring. Pending status is not acceptance.",
            ),
        ]
    )
    return suite
