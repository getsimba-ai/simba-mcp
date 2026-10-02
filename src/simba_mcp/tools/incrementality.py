"""Incrementality test tools backed by the shared Simba API.

Thin over the v1 routes the web app uses. Simba records results analysed elsewhere (geo tests,
owned-media A/B tests, platform lift studies) and derives each test's calibration row for a model;
it fits nothing here.
"""

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context
from pydantic import Field

from ..auth import _client, _page
from ..runtime import AppContext
from ..schemas import APIResult, IncrementalityTestRecord, SubmissionKey

ImportSource = Literal[
    "csv", "meta_conversion_lift", "geox", "geolift", "causalpy", "pymc_marketing"
]

# Permissive schemas: the backend validates every rule and reports field errors (400
# invalid_request); the descriptions say what each key means and its documented bounds.
DesignIntervention = Annotated[
    dict,
    Field(
        json_schema_extra={
            "description": (
                "What changes in the channel's spend and when. start_date (YYYY-MM-DD) is on or "
                "after the model's last training period plus one, at most 13 weekly, 91 daily or "
                "3 monthly periods ahead. durations lists 1-8 distinct candidate lengths in the "
                "model's cadence (1-52 periods); the backend evaluates each and selects one. "
                "spend_change is {mode: pause} (spend to zero), {mode: percent, pct} (pct in "
                "[-100, 500], not 0) or {mode: schedule, baseline: [...], intervention: [...]} "
                "(equal-length currency arrays covering the longest duration). baseline is "
                "{mode: recent_average, periods} (mean spend over the last 4-52 training "
                "periods) or {mode: schedule}; required for pause and percent."
            ),
            "properties": {
                "start_date": {"type": "string", "format": "date"},
                "durations": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 1, "maximum": 52},
                    "minItems": 1,
                    "maxItems": 8,
                },
                "spend_change": {
                    "type": "object",
                    "properties": {
                        "mode": {"type": "string", "enum": ["pause", "percent", "schedule"]},
                        "pct": {"type": "number"},
                        "baseline": {"type": "array", "items": {"type": "number"}},
                        "intervention": {"type": "array", "items": {"type": "number"}},
                    },
                    "required": ["mode"],
                },
                "baseline": {
                    "type": "object",
                    "properties": {
                        "mode": {"type": "string", "enum": ["recent_average", "schedule"]},
                        "periods": {"type": "integer", "minimum": 4, "maximum": 52},
                    },
                    "required": ["mode"],
                },
            },
            "required": ["start_date", "durations", "spend_change"],
        }
    ),
]
DesignInference = Annotated[
    dict,
    Field(
        json_schema_extra={
            "description": (
                "How the planned analysis will be judged. alpha is the two-sided level in "
                "(0, 0.5] (default 0.10); target_power in [0.5, 0.99] (default 0.80) picks the "
                "shortest duration that reaches it. named_effect {value, estimand} asks for the "
                "power to detect an effect you name instead of, or as well as, the model's own "
                "implied effect: value is finite and non-zero, estimand is cumulative, "
                "mean_period, relative or iroas. Omitted defaults are echoed in the result."
            ),
            "properties": {
                "alpha": {"type": "number", "exclusiveMinimum": 0, "maximum": 0.5},
                "target_power": {"type": "number", "minimum": 0.5, "maximum": 0.99},
                "named_effect": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "estimand": {
                            "type": "string",
                            "enum": ["cumulative", "mean_period", "relative", "iroas"],
                        },
                    },
                    "required": ["value", "estimand"],
                },
            },
        }
    ),
]
DesignGeo = Annotated[
    dict,
    Field(
        json_schema_extra={
            "description": (
                "Required for design_type geo_split, ignored otherwise. panel names the "
                "market-level dataset: {kind: uploaded_file | pipeline_version, id, sha256}; the "
                "sha256 must match the stored bytes (400 panel_mismatch otherwise). columns maps "
                "{date, market, outcome, spend?} to the panel's column names. eligible_markets "
                "restricts the markets considered. treatment_share is [low, high], the share of "
                "the panel the treatment group may hold (default [0.2, 0.5]). windows gives "
                "{matching, calibration, validation} lengths in periods (weekly defaults 26, 26, "
                "13; scaled for daily and monthly)."
            ),
            "properties": {
                "panel": {
                    "type": "object",
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": ["uploaded_file", "pipeline_version"],
                        },
                        "id": {"type": "integer"},
                        "sha256": {"type": "string"},
                    },
                    "required": ["kind", "id", "sha256"],
                },
                "columns": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string"},
                        "market": {"type": "string"},
                        "outcome": {"type": "string"},
                        "spend": {"type": "string"},
                    },
                    "required": ["date", "market", "outcome"],
                },
                "eligible_markets": {"type": "array", "items": {"type": "string"}},
                "treatment_share": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "windows": {
                    "type": "object",
                    "properties": {
                        "matching": {"type": "integer", "minimum": 1},
                        "calibration": {"type": "integer", "minimum": 1},
                        "validation": {"type": "integer", "minimum": 1},
                    },
                },
            },
            "required": ["panel", "columns"],
        }
    ),
]


async def recommend_incrementality_tests(
    model_hash: str,
    budget: float | None = None,
    hurdle: float = 1.0,
    limit: int = 5,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Rank channels for experiment investigation using stored posterior marginal returns. Read-only: no fit, test creation or budget changes. Returns {method, basis, score_unit, currency, budget, hurdle, spend_basis, period, approximation_warnings, items, excluded}. Each item carries channel, score, components (mean, sigma, stake, spend_share, crossing_probability, optional contraction), reason_codes, last_test_end, hypothesis and an unavailable design_hint. The score is a normal-approximation local binary perfect-information value, not expected test benefit, experiment budget, portfolio value or forecast lift. budget is a positive exposure scale (default sum of current spend); weights are the mean-active-period spend mix, which need not represent one common calendar period. hurdle is the non-negative marginal-return alternative (default 1). limit is 1-50. Missing posterior means or intervals are explicitly excluded. limited_variance_contraction means contraction from zero to below 0.1; posterior_variance_expanded means negative contraction. Neither proves prior domination. Cross-channel dependence is not modelled. Requires read:results. Test history is unavailable because stored registry records do not establish compatible model/geographical coverage. Requires backend support for test-priorities."""
    return await _client(ctx).workflow_request(
        "GET",
        f"/models/{model_hash}/test-priorities",
        params={"budget": budget, "hurdle": hurdle, "limit": limit},
    )


async def list_incrementality_tests(
    project_id: int,
    type: Literal["geo", "owned_media_ab", "platform_lift", "time_holdout"] | None = None,
    status: Literal["planned", "running", "completed", "invalid"] | None = None,
    channel: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """List a project's recorded (not retired) incrementality tests: {items: [{id, name, type, status, channel, model_channel, start_date, end_date, measured_through, kpi, result, spend, source_tool, has_supplied_row, current_version, used_by}], next_cursor}; used_by counts the model revisions built from the test. Null and negative results are listed like any other. Filter by type, status or channel. Paging is opt-in: pass limit (1-200) and send next_cursor back unchanged; null means the end. Requires the read:models scope."""
    params = {"type": type, "status": status, "channel": channel, **_page(limit, cursor)}
    return await _client(ctx).workflow_request(
        "GET", f"/projects/{project_id}/incrementality-tests", params=params
    )


async def get_incrementality_test(
    test_id: str,
    version: int | None = None,
    model_hash: str | None = None,
    channel: str | None = None,
    confirm_kpi: bool = False,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Read one recorded test: {id, version, record, content_hash, used_by, retired_at}. version reads an older version (default: current). With model_hash (a saved model you can read), the result also carries `calibration`: either {status: "ok", row: {channel, x, delta_x, delta_y, sigma, sigma_low?, sigma_high?}, units, steps, warnings} — the likelihood observation this test gives that model, each step stated — or {status: "refused", reason, message, steps}. A refusal is an answer, not an error: e.g. channel_not_in_model (pass channel, a model activity column), kpi_mismatch (pass confirm_kpi=true only if the test's outcome really is the model's KPI), no_spend, test_not_completed, owned_media_not_calibratable, window_overlaps_holdout. Use the same references in create_model(calibration={tests: [...]}). Requires the read:models scope."""
    client = _client(ctx)
    params = {"version": version}
    test = await client.workflow_request("GET", f"/incrementality-tests/{test_id}", params=params)
    if not model_hash or "_status_code" in test:
        return test
    calibration = await client.workflow_request(
        "GET",
        f"/incrementality-tests/{test_id}/calibration",
        params={
            **params,
            "model_hash": model_hash,
            "channel": channel,
            "confirm_kpi": "true" if confirm_kpi else None,
        },
    )
    if "_status_code" in calibration:
        return calibration
    return {**test, "calibration": calibration}


async def create_incrementality_test(
    project_id: int,
    record: IncrementalityTestRecord,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Record one incrementality test in a project, as analysed in its own tool: its design (geo, owned_media_ab or platform_lift block), dates, KPI, result with interval or sd, and incremental spend. Returns {id, version: 1, record, content_hash}. Set model_channel to the model activity column the test calibrates so it can be used with a model. Validation errors name the field (e.g. "the interval must contain lift_abs"). Not idempotent: calling twice records two tests. type time_holdout is not accepted here: planned time-holdout records are created only through save_incrementality_test_design (the backend refuses them elsewhere), and a status planned record of any type carries no result. Requires the create:models scope."""
    return await _client(ctx).workflow_request(
        "POST", f"/projects/{project_id}/incrementality-tests", record
    )


async def import_incrementality_tests(
    project_id: int,
    source: ImportSource,
    content: str,
    dry_run: bool = True,
    defaults: dict | None = None,
    overrides: dict | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Import tests from another tool's output file: source is csv (Simba's template), meta_conversion_lift (Conversion Lift API results JSON), geox (a meridian-geox analysis result), geolift (GeoLift summary), causalpy (effect summary or lift rows) or pymc_marketing (lift rows); content is the file's text (10 MB max). Returns {records: [{key, record, errors}], created, notes}. dry_run (default true) creates nothing — review each row's errors, then call again with dry_run=false to create the rows without errors (their ids come back in `created`). defaults fills fields the file doesn't carry, e.g. {"channel": "TV", "model_channel": "tv_grps", "kpi": {"kind": "revenue"}}: a GeoX result names no channel or KPI, so its rows fail until those are given. overrides sets fields on one row by the `key` the dry run showed (a cell id, or the 1-based row number), e.g. {"1": {"spend": {"incremental": 25000}}}. Values deep-merge: the source's assumptions, then defaults, then the file, then overrides; a null removes a field. import_invalid means the file isn't that source's format. Requires the create:models scope."""
    payload: dict = {"source": source, "content": content, "dry_run": dry_run}
    if defaults:
        payload["defaults"] = defaults
    if overrides:
        payload["overrides"] = overrides
    return await _client(ctx).workflow_request(
        "POST", f"/projects/{project_id}/incrementality-tests/import", payload
    )


async def design_incrementality_test(
    model_hash: str,
    submission_key: SubmissionKey,
    channel: str,
    design_type: Literal["time_holdout", "geo_split"],
    intervention: DesignIntervention,
    inference: DesignInference | None = None,
    geo: DesignGeo | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Ask a saved, complete MMM what an incrementality test on one of its media channels could detect: queues a bounded calculation that replays the saved posterior and returns {calculation_id, model_hash, status: "queued", submitted_at} at once (202; 200 with the same body when submission_key repeats identical inputs). Poll get_incrementality_test_design until status is complete, failed or cancelled. A complete calculation carries a result whose own state is available, unsupported (e.g. a log-link model), insufficient_evidence or no_feasible_design; none of these is an error, and only available carries numbers (candidates are also returned for no_feasible_design so you can see why nothing met the target). channel is one of the model's nonlinear media channels (400 unknown_channel otherwise). design_type time_holdout pauses or changes the channel's spend for a window and contrasts the outcome with the model's forecast; geo_split needs geo and splits a market panel into treatment and control. intervention gives the start date, candidate durations, spend change and baseline; inference the alpha, target power and an optional named effect; the backend fills and echoes every default. Reuse the same submission_key after a lost response; a new key queues another calculation and the same key with different inputs is refused (409 submission_key_conflict). Refusals: 404 model not found or not readable, 422 model_not_complete, 503 queue_unavailable (nothing is left behind). Nothing is saved or launched and no budget changes; save an available result with save_incrementality_test_design. Requires create:models to submit; polling needs read:results as well, so a key with only create:models can submit but not read."""
    payload: dict = {
        "submission_key": submission_key,
        "channel": channel,
        "design_type": design_type,
        "intervention": intervention,
    }
    if inference is not None:
        payload["inference"] = inference
    if geo is not None:
        payload["geo"] = geo
    return await _client(ctx).workflow_request(
        "POST", f"/models/{model_hash}/test-designs", payload
    )


async def get_incrementality_test_design(
    model_hash: str,
    calculation_id: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Read one test-design calculation: {calculation_id, model_hash, status, submitted_at, started_at, completed_at, request, error, result}. status is operational: queued, running, complete, failed or cancelled; error is {code, message} only when failed (artifact_unreadable, timeout, worker_lost, internal) and a failed calculation carries no numbers. result is present only when complete and is read by its own state, never by key presence: available, unsupported, insufficient_evidence or no_feasible_design, with reasons [{code, detail}] non-empty exactly when not available, plus warnings, assumptions, diagnostics and provenance (method, model artefact, posterior draws, training periods). An available result carries intervention (dates, carryover and measurement end, spend change), model_implied_effect (mean and 94% HDI, parameter uncertainty only; available may be false, e.g. a geo split on a national model, which then gives a national reference only), detectable_effect (cumulative, per-period, relative and, for revenue KPIs, iROAS MDE at the stated alpha and target power), power (at the model mean effect, at the named effect, and assurance), noise, and candidates per duration with the selected one marked. Power here is posterior-averaged: assuming the model is correctly specified and its posterior calibrated, the probability that the pre-specified analysis rejects the null, averaged over the model's forecast uncertainty and observation noise; it is not the probability that this experiment will detect the effect, and a model-implied effect is not a prediction of what the experiment will measure. Requires read:results."""
    return await _client(ctx).workflow_request(
        "GET", f"/models/{model_hash}/test-designs/{calculation_id}"
    )


async def save_incrementality_test_design(
    model_hash: str,
    calculation_id: str,
    project_id: int | None = None,
    name: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Turn an available test-design result into a planned incrementality test record in the registry: returns {id, version, record, content_hash} (201; 200 with the same body when this calculation was already saved). The server builds the record from the stored result (type time_holdout, or geo with treatment and control markets; status planned; source.tool design with the calculation, model artefact and method in source.fields), so only the target project_id (default: the model's project; 400 when the model has none and none is given) and an optional name are sent. Idempotent per calculation. Refusals: 409 result_not_available when the calculation is not complete or its result state is not available, 409 artifact_changed when the model artefact no longer matches the calculation, 403 when you are not the project's owner. A planned record has no measured lift: it cannot calibrate a model (get_incrementality_test reports type_not_calibratable or test_not_completed) and nothing here launches an experiment or changes a budget. Requires create:models and write access to the project."""
    payload: dict = {}
    if project_id is not None:
        payload["project_id"] = project_id
    if name is not None:
        payload["name"] = name
    return await _client(ctx).workflow_request(
        "POST", f"/models/{model_hash}/test-designs/{calculation_id}/save", payload
    )
