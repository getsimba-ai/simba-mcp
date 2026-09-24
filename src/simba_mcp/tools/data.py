"""Data tools backed by the shared Simba API."""

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
        denial = _local_files_denial_reason()
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
    return await _client(ctx).upload_csv(csv_content, name, filename=filename)


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
