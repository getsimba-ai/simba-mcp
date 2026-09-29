"""Data tools backed by the shared Simba API."""

import json
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Context

from ..auth import _client, _local_files_denial_reason, _page
from ..errors import api_error
from ..runtime import MAX_UPLOAD_BYTES, AppContext
from ..schemas import APIResult


async def get_data_schema(ctx: Context[AppContext, Any]) -> APIResult:
    """Get the canonical CSV data schema for Simba MMM input files.

    Returns the JSON Schema specification describing required columns
    (date, KPI, multiplier, hierarchy), media channel column naming
    conventions ({channel}_activity, {channel}_spend), constraints
    (min rows, max file size), and supported date formats.
    """
    return await _client(ctx).get_schema()


async def upload_data(
    csv_content: str = "",
    csv_path: str = "",
    name: str = "",
    filename: str = "",
    roles: dict[str, Any] | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Upload a CSV dataset to Simba for use in model building.

    Provide EXACTLY ONE of csv_content (raw CSV text) or csv_path (a file path
    on the machine running this MCP server). Prefer csv_path for anything
    beyond trivial size — it avoids passing megabytes of CSV through the
    conversation.

    The CSV should follow the canonical schema: one row per time period
    with date, KPI, multiplier, hierarchy, media activity/spend columns,
    and optional control variables.

    IMPORTANT:
    - CSV only (not Excel). Maximum file size: 10 MB (API-enforced).
    - Row minimum: check get_data_schema -> x-simba-constraints.min_rows for
      the declared minimum; enforcement may be more permissive, and the upload
      response's `warnings` field is authoritative. More rows = tighter
      posteriors (104+ weekly rows recommended).
    - Media columns must follow naming: {channel}_activity and {channel}_spend.
    - Use 0 for inactive periods, not blank or NA.
    - csv_path is only available when the server runs locally (stdio). On
      HTTP/SSE deployments it is disabled unless SIMBA_MCP_ALLOW_LOCAL_FILES=1.

    Args:
        csv_content: The full CSV text content (not base64, just raw CSV text).
        csv_path: Path to a .csv file readable by the MCP server process.
        name: Optional dataset name for identification. Defaults to the file
              stem when csv_path is used.
        filename: Optional original filename to record alongside the dataset.
        roles: Optional column roles for get_data_report, stored with the dataset:
               {column: role} or {column: {"role": role, "channel": name}}. Roles
               are declared, never guessed; see get_data_report for the vocabulary.
               An unknown role or a column the CSV lacks is refused.

    Returns the uploaded file ID (needed for create_model), row/column counts,
    and any validation warnings.
    """
    if bool(csv_content) == bool(csv_path):
        return api_error(
            400,
            {
                "error": "Provide exactly one of csv_content or csv_path.",
                "_status_code": 400,
            },
        )
    if csv_path:
        denial = _local_files_denial_reason(ctx)
        if denial:
            return api_error(403, {"error": denial})
        path = Path(csv_path).expanduser()
        if not path.is_file():
            return api_error(400, {"error": f"File not found: {path}"})
        size = path.stat().st_size
        if size > MAX_UPLOAD_BYTES:
            return api_error(
                413,
                {
                    "error": (
                        f"{path.name} is {size / 1024 / 1024:.1f} MB — over the API's "
                        f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB ingest limit. "
                        "Aggregate or trim the file first."
                    ),
                    "_status_code": 413,
                },
            )
        try:
            csv_content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            return api_error(
                400,
                {
                    "error": "Cannot read CSV as UTF-8. Check file access and encoding, or use csv_content."
                },
            )
        if not name:
            name = path.stem
        if not filename:
            filename = path.name
    return await _client(ctx).upload_csv(csv_content, name, filename=filename, roles=roles)


async def list_uploads(
    limit: int = 50,
    offset: int = 0,
    name: str = "",
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """List the datasets in your workspace (newest first) — every source,
    not just API uploads: dashboard/manual uploads and pipeline-ingested
    datasets appear too (see source_type per file).

    Returns {files, count, limit, offset} where each file has: id (the
    uploaded_file_id create_model needs), filename, original_filename,
    source_type, row_count, column_count, created_at. Here `count` IS the
    true total matching the filter (unlike list_runs, where it is the page
    length). Column names/dtypes are not in the listing — fetch one upload
    with get_upload for those.

    Args:
        limit: Page size (API clamps to 1-500; default 50).
        offset: Rows to skip (paging).
        name: Optional case-insensitive substring filter on the original
              filename.
    """
    return await _client(ctx).list_uploads(limit=limit, offset=offset, name=name)


async def list_pipelines(
    limit: int | None = None,
    cursor: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """List the data pipelines this key's owner has, most recently updated first, each with id, pipeline_hash, name, description, version_count and latest_version (id, version, created_at, row_count, checksum). Identity only: no definitions, parameters or output data. Use a version id as pipeline_version_id in get_recipe_draft_template. Requires the ingest scope; the same ownership rule as the app. Paging is opt-in: pass limit (1-200) to receive a page and next_cursor; send that cursor back unchanged for the next page; null next_cursor means the end."""
    return await _client(ctx).workflow_request("GET", "/pipelines", params=_page(limit, cursor))


async def list_pipeline_versions(
    pipeline_ref: str,
    limit: int | None = None,
    cursor: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """List the saved versions of one owned pipeline (by pipeline_hash or id), newest first: id, version, created_at, row_count, column_count, column names and checksum. The checksum is the exact source identity a recipe draft freezes. Never returns the data itself; fetch a draft template with pipeline_version_id for that. Paging is opt-in: pass limit (1-200) to receive a page and next_cursor; send that cursor back unchanged for the next page; null next_cursor means the end."""
    return await _client(ctx).workflow_request(
        "GET", f"/pipelines/{pipeline_ref}/versions", params=_page(limit, cursor)
    )


async def run_pipeline(
    pipeline_ref: str,
    start_date: str | None = None,
    end_date: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Start a refresh of one owned data pipeline (by pipeline_hash or id). Returns {run_id, status: "queued"} at once; the run executes on the server as the pipeline's owner with its saved connections. Poll get_pipeline_run until status is succeeded or failed (every few seconds; warehouse runs can take minutes, and a run stops at 30 minutes). Optional start_date / end_date (YYYY-MM-DD) limit the source steps to that range. One run per pipeline at a time: if one is already queued or running you get run_in_progress with that run_id — poll it instead of starting another. Each successful run saves a new pipeline version. Requires the create:models scope."""
    payload = {k: v for k, v in {"start_date": start_date, "end_date": end_date}.items() if v}
    return await _client(ctx).workflow_request(
        "POST", f"/pipelines/{pipeline_ref}/runs", payload=payload
    )


async def get_pipeline_run(
    pipeline_ref: str,
    run_id: int,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Get one run of an owned pipeline: {run_id, status (queued | running | succeeded | failed), started_at, finished_at (UTC), version_id, error_code, error}. On success version_id is the new saved version — pass it as pipeline_version_id to get_recipe_draft_template to build on the refreshed data. On failure error_code says why: execution_failed (a source or transform failed; error names it), no_output, timeout, interrupted or not_started (start it again), not_queued, owner_blocked, unexpected. Scheduled runs are polled the same way. Requires the create:models scope."""
    return await _client(ctx).workflow_request("GET", f"/pipelines/{pipeline_ref}/runs/{run_id}")


async def set_pipeline_schedule(
    pipeline_ref: str,
    cadence: str,
    hour_utc: int,
    enabled: bool,
    weekday: int | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Replace the refresh schedule of one owned pipeline. cadence is "daily" or "weekly"; hour_utc is a whole UTC hour 0-23; weekday (0 = Monday … 6 = Sunday) is required for weekly and must be omitted for daily; enabled false pauses the schedule and keeps its settings. Returns the schedule with next_run_at (UTC). Each due slot starts one ordinary run (poll it with get_pipeline_run); a slot is skipped while a run of that pipeline is still going. After a scheduled run succeeds the pipeline keeps its newest 30 versions; a version a model or recipe was built from is never removed. Requires the create:models scope."""
    payload = {"cadence": cadence, "hour_utc": hour_utc, "enabled": enabled}
    if weekday is not None:
        payload["weekday"] = weekday
    return await _client(ctx).workflow_request(
        "PUT", f"/pipelines/{pipeline_ref}/schedule", payload=payload
    )


async def get_upload(
    file_id: int,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Get one uploaded dataset's details, including its column schema.

    Returns id, filename, original_filename, source_type, mime_type,
    file_size, row_count, column_count, columns ([{name, dtype}, ...] — use
    these to build create_model's channel/control column arguments without
    re-reading the CSV), and created_at.

    Args:
        file_id: The upload's id, from upload_data's response or list_uploads.
    """
    return await _client(ctx).get_upload(file_id)


async def get_backend_capabilities(ctx: Context[AppContext, Any]) -> APIResult:
    """Discover this caller's connected backend features before planning work.

    Returns only backend advertisements: model families, transformations, priors
    and workflow operations. A missing advertisement is unknown, not unsupported.
    Check each field; an advertised feature still requires permission and budget.
    No model is created and capabilities are not cached across callers.
    """
    schema = await _client(ctx).get_schema()
    if schema.get("_status_code", 200) >= 400:
        return schema
    keys = ("x-simba-model-capabilities", "x-simba-workflow-capabilities")
    advertisements = {key: schema[key] for key in keys if isinstance(schema.get(key), dict)}
    return {
        "source": "/api/v1/ingest/schema",
        "advertisements": advertisements,
        "unknown": [key for key in keys if key not in advertisements],
        "guidance": "Missing fields are unknown. Backend authorization and validation remain authoritative.",
    }


async def get_data_report(
    dataset_id: int,
    start: str = "",
    end: str = "",
    granularity: str = "native",
    group_by: str = "",
    hierarchy: str = "",
    metrics: list[str] | None = None,
    roles: dict[str, Any] | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Report actual data from a stored dataset: any window, any grain, by brand, channel or dimension.

    Reads the dataset itself (every column, any date range) rather than a fitted model's
    training window. Use it for "sales and TV spend in the North region for August, by week".

    Roles are DECLARED, never guessed from column names. Declare them with upload_data(roles=...)
    or per request with `roles`. Without a declaration only the schema's own naming rules apply:
    a column named `date`, `{channel}_spend` and `{channel}_activity`. Every other column is
    reported as role "unknown" and is not aggregated — declare the KPI and hierarchy columns.

    Role vocabulary (aggregation, unit) — also in get_data_schema under x-simba-roles:
    - kpi (sum), spend (sum, currency), activity (sum), multiplier (mean)
    - outcome:online_sales|store_sales|margin (sum, currency), outcome:orders|new_customers (sum)
    - media:impressions|clicks|grps (sum; give a channel: {"role": "media:grps", "channel": "tv"})
    - control:price|rate|index (mean), control:stock (each brand's last value, summed)
    - hierarchy, dimension:market|product|campaign (keys for filtering and group_by)
    - date

    Buckets: week = ISO week from Monday; month/quarter = calendar. A weekly row counts in the
    month of its week-start date. The response's meta.aggregation states every rule applied.

    Args:
        dataset_id: The uploaded file id (from upload_data or list_uploads). Registered
                    pipeline outputs are uploaded files too.
        start, end: Optional ISO dates (YYYY-MM-DD), inclusive.
        granularity: "native" (default), "week", "month" or "quarter".
        group_by: "hierarchy", "channel", or a dimension role such as "dimension:market".
        hierarchy: Keep only this brand/region value.
        metrics: Roles or role families to include, e.g. ["kpi", "spend", "outcome:orders"] or
                 ["control"]. Default: every metric role present.
        roles: {column: role | {"role", "channel"}} overriding roles stored at upload.

    Returns {dataset: {id, name, source, version, sha256, data_through}, granularity,
    rows: [{period_start, period_end, group, metric, value, unit}], meta: {basis: "dataset",
    aggregation, roles, channels}}. Errors carry a code: dataset_not_found (404),
    invalid_report_request (400), report_too_large (413, over 10,000 rows — narrow the window
    or coarsen the granularity).
    """
    params: dict[str, str] = {"granularity": granularity or "native"}
    for key, value in (
        ("start", start),
        ("end", end),
        ("group_by", group_by),
        ("hierarchy", hierarchy),
    ):
        if value:
            params[key] = value
    if metrics:
        params["metrics"] = ",".join(metrics)
    if roles:
        params["roles"] = json.dumps(roles)
    return await _client(ctx).get_data_report(dataset_id, params)
