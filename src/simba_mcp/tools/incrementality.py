"""Incrementality test tools backed by the shared Simba API.

Thin over the v1 routes the web app uses. Simba records results analysed elsewhere (geo tests,
owned-media A/B tests, platform lift studies) and derives each test's calibration row for a model;
it fits nothing here.
"""

from typing import Any, Literal

from mcp.server.mcpserver import Context

from ..auth import _client, _page
from ..runtime import AppContext
from ..schemas import APIResult, IncrementalityTestRecord

ImportSource = Literal[
    "csv", "meta_conversion_lift", "geox", "geolift", "causalpy", "pymc_marketing"
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
    type: Literal["geo", "owned_media_ab", "platform_lift"] | None = None,
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
    """Record one incrementality test in a project, as analysed in its own tool: its design (geo, owned_media_ab or platform_lift block), dates, KPI, result with interval or sd, and incremental spend. Returns {id, version: 1, record, content_hash}. Set model_channel to the model activity column the test calibrates so it can be used with a model. Validation errors name the field (e.g. "the interval must contain lift_abs"). Not idempotent: calling twice records two tests. Requires the create:models scope."""
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
