"""Independently authored synthetic cases for documented public tool contracts."""

from copy import deepcopy

from .contracts import Case, Exchange, Step


def cases() -> list[Case]:
    def exchange(method, path, response, body=None, **kwargs):
        return Exchange(
            method=method, path="/api/v1" + path, response=response, body=body, **kwargs
        )

    def step(tool, arguments, exchanges, expected, **kwargs):
        return Step(
            tool=tool,
            arguments=deepcopy(arguments),
            exchanges=deepcopy(exchanges),
            expected=deepcopy(expected),
            **kwargs,
        )

    status = {"model_hash": "model-example", "status": "complete"}
    get_status = lambda **kw: exchange("GET", "/models/model-example/status", status, **kw)
    model_args = {
        "uploaded_file_id": 1,
        "date_column": "week",
        "kpi_column": "units",
        "hierarchy_column": "brand",
        "channels": [
            {"name": "Search", "activity_column": "search_clicks", "spend_column": "search_spend"}
        ],
        "seasonality": True,
        "sampler": {"chains": 2, "tune": 100, "n_samples": 100},
    }
    model_body = {
        "data_source": {"uploaded_file_id": 1},
        "date_column": "week",
        "kpi_column": "units",
        "hierarchy_column": "brand",
        "channels": [
            {"name": "Search", "activity_column": "search_clicks", "spend_column": "search_spend"}
        ],
        "control_columns": [],
        "total_media_effect": "Other",
        "config": {
            "trend": False,
            "seasonality": True,
            "likelihood": "normal",
            "sampler": {"chains": 2, "tune": 100, "n_samples": 100},
        },
    }
    created = {"model_hash": "model-example", "status": "pending"}
    prior = {"channel": "Search", "mean": 0.2, "sd": 0.1}
    advanced_args = {**deepcopy(model_args), "priors": [prior]}
    advanced_body = {**deepcopy(model_body), "priors": [deepcopy(prior)]}
    optimiser = {
        "total_budget": 1200.0,
        "num_periods": 2,
        "gamma": 0.1,
        "currency": "GBP",
        "bounds": {"search_clicks": {"lower": 20, "upper": 100}},
        "laydown_weights": {"search_clicks": [1, 2]},
        "period_cpm": {"search_clicks": [3, 4]},
        "objective": "profit",
        "forward_margin": 0.25,
    }
    snapshot = {"version": 1, "configuration": {"extension": {"preserve": [1, 2]}}}
    draft_id = "00000000-0000-4000-8000-000000000001"
    draft = {"id": draft_id, "version": 1, "snapshot": snapshot}
    launch = {
        "revision_id": "revision-example",
        "policy_id": "policy-example",
        "submission_key": "00000000-0000-4000-8000-000000000002",
    }
    review = {
        "evaluations": [
            {
                "id": "evaluation-example",
                "report": {
                    "checks": [
                        {
                            "metric": "holdout",
                            "status": "not_evaluated",
                            "basis": {"reason": "not_collected"},
                        }
                    ]
                },
            }
        ]
    }
    result = {
        "channel_summary": [
            {
                "Channel": "search_clicks",
                "ROI": 2.0,
                "contribution_share": 0.1,
                "unit": "units",
                "interval": [0.05, 0.15],
            }
        ]
    }
    suite = [
        Case(
            id="analyse_model",
            purpose="Preserve identifiers, units, intervals and distinct measures",
            steps=[
                step("get_model_status", {"model_hash": "model-example"}, [get_status()], status),
                step(
                    "get_model_results",
                    {"model_hash": "model-example"},
                    [
                        exchange(
                            "GET", "/models/model-example/results", result, query={"format": "json"}
                        )
                    ],
                    result,
                ),
            ],
        ),
        Case(
            id="create_mmm",
            purpose="Forward requested settings with exactly one creation",
            steps=[
                step(
                    "create_model",
                    model_args,
                    [exchange("POST", "/models", created, model_body)],
                    created,
                ),
                step("get_model_status", {"model_hash": "model-example"}, [get_status()], status),
            ],
        ),
        Case(
            id="advanced_priors",
            purpose="Preserve explicitly supplied priors",
            steps=[
                step(
                    "create_model",
                    advanced_args,
                    [exchange("POST", "/models", created, advanced_body)],
                    created,
                )
            ],
        ),
        Case(
            id="optimiser_setup",
            purpose="Preserve budget currency, exact keys, bounds and objective",
            steps=[
                step(
                    "run_optimizer",
                    {"model_hash": "model-example", **optimiser},
                    [
                        exchange(
                            "POST",
                            "/models/model-example/optimize",
                            {"run_id": "optim-example"},
                            deepcopy(optimiser),
                        )
                    ],
                    {"run_id": "optim-example"},
                )
            ],
        ),
        Case(
            id="draft_edit",
            purpose="Preserve nested authoring fields and concurrency version",
            steps=[
                step(
                    "create_recipe_draft",
                    {
                        "study_id": "study-example",
                        "draft_id": draft_id,
                        "name": "Synthetic",
                        "snapshot": snapshot,
                    },
                    [
                        exchange(
                            "POST",
                            "/studies/study-example/recipe-drafts",
                            draft,
                            {"id": draft_id, "name": "Synthetic", "snapshot": snapshot},
                        )
                    ],
                    draft,
                ),
                step(
                    "update_recipe_draft",
                    {
                        "draft_id": draft_id,
                        "expected_version": 1,
                        "name": "Revised",
                        "snapshot": snapshot,
                    },
                    [
                        exchange(
                            "PATCH",
                            f"/recipe-drafts/{draft_id}",
                            {**draft, "version": 2},
                            {"expected_version": 1, "name": "Revised", "snapshot": snapshot},
                        )
                    ],
                    {"version": 2},
                ),
            ],
        ),
        Case(
            id="study_review",
            purpose="Missing evidence stays unevaluated, review performs no write",
            steps=[
                step(
                    "list_study_evaluations",
                    {"run_id": "run-example", "expand": ["report"]},
                    [
                        exchange(
                            "GET",
                            "/study-runs/run-example/evaluations",
                            review,
                            query={"expand": "report"},
                        )
                    ],
                    review,
                )
            ],
        ),
        Case(
            id="stale_revision",
            purpose="A stale publication refuses without launch or retry",
            steps=[
                step(
                    "publish_recipe_draft",
                    {
                        "draft_id": draft_id,
                        "expected_version": 1,
                        "publication_id": "00000000-0000-4000-8000-000000000003",
                        "reason": "Synthetic",
                    },
                    [
                        exchange(
                            "POST",
                            f"/recipe-drafts/{draft_id}/publish",
                            {"code": "stale_version"},
                            {
                                "expected_version": 1,
                                "publication_id": "00000000-0000-4000-8000-000000000003",
                                "reason": "Synthetic",
                            },
                            status=412,
                        )
                    ],
                    {"_status_code": 412},
                    is_error=True,
                )
            ],
        ),
        Case(
            id="wrong_channel",
            purpose="Backend refusal of unknown channel is preserved",
            steps=[
                step(
                    "run_optimizer",
                    {"model_hash": "model-example", **optimiser},
                    [
                        exchange(
                            "POST",
                            "/models/model-example/optimize",
                            {"code": "unknown_channel"},
                            deepcopy(optimiser),
                            status=400,
                        )
                    ],
                    {"_status_code": 400},
                    is_error=True,
                )
            ],
        ),
        Case(
            id="rate_limit",
            purpose="Retry a read after a rate limit",
            steps=[
                step(
                    "get_model_status",
                    {"model_hash": "model-example"},
                    [
                        exchange(
                            "GET",
                            "/models/model-example/status",
                            {"code": "rate_limited"},
                            status=429,
                        ),
                        get_status(),
                    ],
                    status,
                )
            ],
        ),
        Case(
            id="outage",
            purpose="Bound retries when all read attempts fail",
            steps=[
                step(
                    "get_model_status",
                    {"model_hash": "model-example"},
                    [
                        exchange(
                            "GET",
                            "/models/model-example/status",
                            {"code": "unavailable"},
                            status=503,
                        )
                        for _ in range(3)
                    ],
                    {"_status_code": 503},
                    is_error=True,
                )
            ],
        ),
        Case(
            id="uncertain_launch",
            purpose="No implicit replay; explicit recovery retains submission key",
            steps=[
                step(
                    "launch_study_run",
                    {"study_id": "study-example", **launch},
                    [exchange("POST", "/studies/study-example/runs", {}, launch, fault="timeout")],
                    {"_status_code": 503},
                    is_error=True,
                ),
                step(
                    "launch_study_run",
                    {"study_id": "study-example", **launch},
                    [
                        exchange(
                            "POST", "/studies/study-example/runs", {"id": "run-example"}, launch
                        )
                    ],
                    {"id": "run-example"},
                ),
            ],
        ),
        Case(
            id="cancellation",
            purpose="Cancellation propagates without another attempt",
            steps=[
                step(
                    "get_model_status",
                    {"model_hash": "model-example"},
                    [get_status(fault="cancel")],
                    {},
                    cancelled=True,
                )
            ],
        ),
        Case(
            id="invalid_arguments",
            purpose="Invalid typed arguments refuse before backend I/O",
            steps=[
                step(
                    "create_model",
                    {**model_args, "uploaded_file_id": "not-an-integer"},
                    [],
                    {"_status_code": 422},
                    is_error=True,
                )
            ],
        ),
    ]
    missing = {**deepcopy(model_args), "control_priors": [{"name": "price", "transform": "N"}]}
    suite.append(
        Case(
            id="missing_capability",
            purpose="Unsupported control priors never create a model",
            steps=[
                step(
                    "create_model",
                    missing,
                    [exchange("GET", "/ingest/schema", {})],
                    {},
                    is_error=True,
                    tool_error="does not advertise control_priors version 1 support",
                )
            ],
        )
    )
    return suite
