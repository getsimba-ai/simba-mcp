"""Campaign facts tools backed by the shared Simba API.

Thin over the v1 routes the web app uses. Campaign and ad-set facts (spend, impressions, clicks,
the platform's own conversions and value) arrive through a Simba data pipeline that a human has
registered as the campaign facts source in the app; these tools read them and declare which
model channel each campaign counts towards. Nothing here fits a model.
"""

from typing import Any, Literal

from mcp.server.mcpserver import Context

from ..auth import _client, _page
from ..runtime import AppContext
from ..schemas import APIResult

Platform = Literal["meta", "google_ads", "tiktok", "other"]


async def list_campaigns(
    model_hash: str,
    platform: Platform | None = None,
    unmapped_only: bool = False,
    start: str | None = None,
    end: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """List the campaigns in the campaign facts, each with its totals and the model channel it
    counts towards for this model.

    The channel is DECLARED in the model's campaign map (set_campaign_mapping), never inferred:
    a campaign no map row covers is `status: "unmapped"` with `channel: null`, is listed with its
    spend, and is not counted towards any channel. `suggested_channel` is a hint from the
    platform's own label and the campaign's name (null when nothing is clear); it does nothing
    until it is written into the map.

    Returns {campaigns: [{platform, account_id, campaign_id, campaign_name, adsets, spend,
    impressions, clicks, platform_conversions, platform_value, platform_channel_type, first_seen,
    last_seen, channel, suggested_channel, status: "mapped" | "unmapped"}], window: {start, end},
    currency, as_of, next_cursor (only when `limit` was given)}. Sorted by platform, account and
    campaign id. Totals cover the window (default: every stored day).

    Args:
        model_hash: The model whose map decides each campaign's channel (the hash of a fitted MMM).
        platform: Keep one platform: meta, google_ads, tiktok or other.
        unmapped_only: Only campaigns without a channel for this model.
        start, end: Optional ISO dates (YYYY-MM-DD), inclusive, for the totals.
        limit: Page size (1-200). Without it every campaign is returned.
        cursor: The previous page's next_cursor.

    Errors carry a code: model_not_found (404). An empty list means no pipeline is registered as
    the campaign facts source yet, or it has not run; registration happens in the app.
    """
    params: dict = {"model": model_hash, **_page(limit, cursor)}
    if platform:
        params["platform"] = platform
    if unmapped_only:
        params["unmapped_only"] = "true"
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    return await _client(ctx).workflow_request("GET", "/campaigns", params=params)


async def get_campaign_report(
    model_hash: str | None = None,
    start: str | None = None,
    end: str | None = None,
    granularity: Literal["native", "week", "month", "quarter", "year"] = "native",
    group_by: Literal["platform", "channel", "campaign", "adset"] | None = None,
    platform: Platform | None = None,
    channel: str | None = None,
    campaign_id: str | None = None,
    metrics: list[str] | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Report the campaign facts over any window, at any grain, by platform, model channel,
    campaign or ad set.

    The same report engine as get_data_report, over the campaign facts: spend, media:impressions,
    media:clicks, outcome:platform_conversions, outcome:platform_value and, where a source fills
    them, outcome:last_click_conversions and outcome:last_click_value. These are the PLATFORMS'
    own attributed numbers, not Simba's incremental attribution.

    `group_by: "channel"` groups by the model channel each campaign counts towards under the
    model's map (give model_hash); spend of unmapped campaigns appears as its own group,
    "unmapped", and is never dropped or guessed into a channel. Without model_hash every row is
    "unmapped".

    Returns {granularity, data_through, rows: [{period_start, period_end, group, metric, value,
    unit}], meta: {basis, aggregation, roles, channels}, as_of, source_versions, currency}.
    `as_of` is when the facts were last ingested; `source_versions` the pipeline versions they
    came from.

    Args:
        model_hash: The model whose map decides the channels (optional; needed for group_by=channel).
        start, end: Optional ISO dates (YYYY-MM-DD), inclusive.
        granularity: "native" (daily, as stored), "week", "month", "quarter" or "year".
        group_by: "platform", "channel", "campaign" or "adset". Default: one total per period.
        platform, channel, campaign_id: Filters applied before grouping.
        metrics: Roles to include, e.g. ["spend", "outcome:platform_conversions"]. Default: all.

    Errors carry a code: campaign_facts_empty (404, nothing matches), invalid_report_request
    (400), report_too_large (413: narrow the window or coarsen the granularity).
    """
    params: dict = {"granularity": granularity or "native"}
    for key, value in (
        ("model", model_hash),
        ("start", start),
        ("end", end),
        ("group_by", group_by),
        ("platform", platform),
        ("channel", channel),
        ("campaign_id", campaign_id),
    ):
        if value:
            params[key] = value
    if metrics:
        params["metrics"] = ",".join(metrics)
    return await _client(ctx).workflow_request("GET", "/campaigns/report", params=params)


async def set_campaign_mapping(
    model_hash: str,
    rows: list[dict[str, Any]],
    tolerance: float = 0.05,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Replace the model's campaign map: which model channel each campaign counts towards.

    Each row is {platform, campaign_id | name_pattern, channel, valid_from?, valid_to?}: exactly
    one of `campaign_id` (the platform's id, exact) or `name_pattern` (a glob on the campaign
    name, e.g. "YouTube*", case-insensitive); `channel` must be one of the model's channel names
    (as in get_model_results); dates are ISO and optional (open-ended when absent). An exact-id
    row beats any pattern row. The whole map is replaced by `rows`; send every row you want kept.

    Refused (422, code campaign_map_invalid, nothing saved) when a channel is not the model's
    (the error names the closest one), when a campaign would count towards two channels on any
    date (two exact rows on one campaign with overlapping dates, or two patterns matching one
    campaign with overlapping dates; `conflicts` lists them), or when a row is malformed.

    Returns the map report: {map, unmapped: [{platform, campaign_id, campaign_name, spend,
    first_seen, last_seen, platform_channel_type, suggested_channel}], conflicts: [], drift:
    [{channel, campaign_spend, model_spend, ratio, over_tolerance, campaigns}], tolerance,
    currency, currency_mismatch, window, channels}. `drift` compares the spend of the campaigns
    mapped to each channel with the model's own spend for that channel over the dates both have;
    `over_tolerance` is a WARNING (the map is saved), usually a campaign that belongs elsewhere
    or model data that stops before the campaigns do. Unmapped campaigns stay listed and are not
    counted; map them in a later call.

    Args:
        model_hash: The fitted MMM the map belongs to.
        rows: The complete map.
        tolerance: The drift warning threshold as a fraction (default 0.05).
    """
    return await _client(ctx).workflow_request(
        "PUT",
        "/campaigns/map",
        {"rows": rows, "tolerance": tolerance},
        params={"model": model_hash},
    )


async def get_campaign_incrementality(
    model_hash: str,
    start: str | None = None,
    end: str | None = None,
    level: Literal["campaign", "adset"] = "campaign",
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Incremental ROAS per campaign (or ad set), beside the platform's own ROAS and last-click
    ROAS, by pushing the model's channel incrementality down through the platform's attribution.

    THE ASSUMPTION, FIRST. Simba measures incrementality at channel grain. For each model channel
    over the window, the incrementality factor = the channel's MMM incremental revenue (the
    model's per-period rows, under its fitted attribution convention) / the platform-attributed
    value of the campaigns mapped to that channel. Each campaign's incremental ROAS is that
    factor x its platform ROAS, so campaign incremental revenue sums to the channel's. This
    assumes the platform over-credits every campaign in a channel equally. It does not:
    retargeting and brand search are over-credited more, so one factor flatters them. The
    response warns when such campaigns share a channel with prospecting
    (`retargeting_shares_channel_factor`); the remedies are to map them to their own model
    channel (set_campaign_mapping) or to calibrate the factor with an incrementality test.
    Nothing here is a causal per-campaign measurement; every row says how it was made.

    Per row, `method` is "attribution_scaled" or, when a channel's campaigns carry no platform
    value, "spend_share" (the channel's incremental revenue shared by spend). A campaign without
    platform value in a channel that has some gets `iroas: null` and is named
    (`platform_value_missing`); it is never given a share. `factor_source` is "mmm" or "test":
    a completed incrementality test in the model's project that names the channel and overlaps
    the window replaces the model's factor (lift in revenue units / the channel's platform value
    during the test); `factor_mmm` stays beside it.

    `interval` is "pending" (the 94% bands come from the model's posterior draws, computed by a
    background job the first time a window is asked for; ask again in a few minutes), "ready"
    (`factor_interval` per channel, `iroas_hdi` and `incremental_revenue_hdi` per row) or
    "unavailable" (`interval_reason` says why; point estimates stand, no band is invented).
    `uninformative` warns when a channel's band spans zero.

    Returns {model_hash, window: {start, end}, level, currency, interval, interval_reason,
    channels: [{channel, factor, factor_source, factor_mmm, factor_interval, revenue_interval,
    factor_draws_mean, method, mmm_revenue, platform_value, spend, campaigns, test, warnings}],
    rows: [{platform, account_id, campaign_id, campaign_name, adset_id, channel, spend,
    platform_value, last_click_value, days, platform_roas, last_click_roas, incremental_revenue,
    iroas, incremental_revenue_hdi, iroas_hdi, method, factor_source}], unmapped: [{..., spend,
    platform_roas, last_click_roas}], warnings: [{code, message, channel?, campaigns?,
    reason?}], provenance: {source_versions, as_of, map_version, attribution_convention, link}}.
    Warning codes: retargeting_shares_channel_factor, platform_value_missing, kpi_not_revenue,
    currency_mismatch, uninformative, unmapped_spend, interval_unavailable,
    test_override_skipped.

    Args:
        model_hash: A fitted MMM with a campaign map (set_campaign_mapping).
        start, end: Optional ISO dates (YYYY-MM-DD), inclusive. Default: the overlap of the
            model's data and the campaign facts.
        level: "campaign" (default) or "adset"; ad-set rows inherit their campaign's channel
            and factor and sum to the campaign row.

    Errors carry a code: model_not_found (404), campaign_facts_empty (404: no facts, or none in
    the window), invalid_window (400: empty or reversed; the body gives both spans),
    model_not_mmm (400: a VAR model has no channel revenue rows), model_incomplete (400).
    """
    params: dict = {"model": model_hash, "level": level or "campaign"}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    return await _client(ctx).workflow_request("GET", "/campaigns/incrementality", params=params)
