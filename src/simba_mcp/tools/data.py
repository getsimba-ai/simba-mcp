"""Data tools backed by the Simba API."""

from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from ..auth import _client, _local_files_denial_reason
from ..runtime import AppContext

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


async def get_data_schema(ctx: Context[AppContext, Any]) -> dict:
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
) -> dict:
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
        return {
            "error": "Provide exactly one of csv_content or csv_path.",
            "_status_code": 400,
        }
    if csv_path:
        denial = _local_files_denial_reason()
        if denial:
            return {"error": denial, "_status_code": 403}
        path = Path(csv_path).expanduser()
        if not path.is_file():
            return {"error": f"File not found: {path}", "_status_code": 400}
        size = path.stat().st_size
        if size > MAX_UPLOAD_BYTES:
            return {
                "error": (
                    f"{path.name} is {size / 1024 / 1024:.1f} MB — over the API's "
                    f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB ingest limit. "
                    "Aggregate or trim the file first."
                ),
                "_status_code": 413,
            }
        csv_content = path.read_text(encoding="utf-8-sig")
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
) -> dict:
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


async def get_upload(
    file_id: int,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Get one uploaded dataset's details, including its column schema.

    Returns id, filename, original_filename, source_type, mime_type,
    file_size, row_count, column_count, columns ([{name, dtype}, ...] — use
    these to build create_model's channel/control column arguments without
    re-reading the CSV), and created_at.

    Args:
        file_id: The upload's id, from upload_data's response or list_uploads.
    """
    return await _client(ctx).get_upload(file_id)


def register(mcp: MCPServer) -> None:
    mcp.tool()(get_data_schema)
    mcp.tool()(upload_data)
    mcp.tool()(list_uploads)
    mcp.tool()(get_upload)
