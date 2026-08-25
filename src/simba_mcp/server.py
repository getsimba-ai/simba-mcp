"""
Simba MCP Server — exposes Simba's API v1 as MCP tools.

Tools allow AI assistants (Claude, Cursor, etc.) to interact with
Marketing Mix Models: upload data, create models, check status,
get results, and run budget optimizations.

Run locally:  simba-mcp
Run remote:   uvicorn simba_mcp.server:app --host 0.0.0.0 --port 8100
"""

import importlib.metadata
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from .api_client import SimbaAPIClient

logger = logging.getLogger(__name__)

# The API's actual ingest cap (src/api/v1/ingest.py: MAX_INGEST_SIZE_BYTES).
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# csv_path reads files from the machine the MCP server runs on. That is the
# caller's own machine in stdio mode, but NOT in HTTP/SSE deployments — there
# it would read the server host's filesystem, so it defaults off. Override
# with SIMBA_MCP_ALLOW_LOCAL_FILES=1/0.
_serving_http = False


def set_http_mode(enabled: bool = True) -> None:
    """Mark the server as running over a network transport (HTTP/SSE)."""
    global _serving_http
    _serving_http = enabled


def _local_files_allowed() -> bool:
    return _local_files_denial_reason() is None


def _local_files_denial_reason() -> str | None:
    """Return an error message if csv_path reads are disallowed, else None.

    Distinguishes an explicit SIMBA_MCP_ALLOW_LOCAL_FILES=0 from the default
    HTTP/SSE disable, so callers get accurate remediation guidance.
    """
    env = os.environ.get("SIMBA_MCP_ALLOW_LOCAL_FILES", "").strip().lower()
    if env in ("1", "true", "yes"):
        return None
    if env in ("0", "false", "no"):
        return (
            "csv_path is disabled because SIMBA_MCP_ALLOW_LOCAL_FILES is set "
            f"to {env!r}. Pass csv_content instead, or set "
            "SIMBA_MCP_ALLOW_LOCAL_FILES=1 to allow local file reads."
        )
    if _serving_http:
        return (
            "csv_path is disabled on network transports (HTTP/SSE) because "
            "it reads the server host's filesystem, not yours. Pass "
            "csv_content instead, or set SIMBA_MCP_ALLOW_LOCAL_FILES=1 "
            "on the server if this is intentional."
        )
    return None


@dataclass
class AppContext:
    client: SimbaAPIClient


@asynccontextmanager
async def app_lifespan(server: MCPServer) -> AsyncIterator[AppContext]:
    # Under SDK v2's streamable HTTP the lifespan enters ONCE per process and
    # this AppContext is shared by every session (v1 entered it per-session).
    # Safe here: the client holds only the server-wide internal API key and a
    # stateless httpx connection pool — no per-session state may ever be
    # added to AppContext without revisiting this.
    base_url = os.environ.get("SIMBA_API_URL", "http://localhost:5005")
    api_key = os.environ.get("SIMBA_API_KEY", "")
    if not api_key:
        logger.warning(
            "SIMBA_API_KEY is not set — all API calls will return an authentication error. "
            "This MCP server requires a Simba account. "
            "Book a call to get started: https://calendly.com/niall-oulton"
        )
    client = SimbaAPIClient(base_url, api_key)
    try:
        yield AppContext(client=client)
    finally:
        await client.close()


def _own_version() -> str:
    """simba-mcp's own package version for the initialize handshake (#41).

    v2 servers with no version report "" — not the SDK fallback — so losing
    this kwarg would silently regress #41 in a new way.
    """
    try:
        return importlib.metadata.version("simba-mcp")
    except importlib.metadata.PackageNotFoundError:  # running from source without install
        return "0.0.0"


# Every argument keyword: the v2 constructor order is (name, title,
# description, instructions, ...) — a positional instructions lands in title.
mcp = MCPServer(
    name="Simba MMM",
    version=_own_version(),
    instructions=(
        "Simba is a Bayesian Marketing Mix Modeling (MMM) platform. "
        "Use these tools to upload marketing data, build MMM models, "
        "check fitting progress, retrieve results (channel ROI, contributions, "
        "model diagnostics), and run budget optimizations."
    ),
    lifespan=app_lifespan,
)


def _client(ctx: Context[AppContext, Any]) -> SimbaAPIClient:
    return ctx.request_context.lifespan_context.client


# ---------------------------------------------------------------------------
# Tool 1: get_data_schema
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_data_schema(ctx: Context[AppContext, Any]) -> dict:
    """Get the canonical CSV data schema for Simba MMM input files.

    Returns the JSON Schema specification describing required columns
    (date, KPI, multiplier, hierarchy), media channel column naming
    conventions ({channel}_activity, {channel}_spend), constraints
    (min rows, max file size), and supported date formats.
    """
    return await _client(ctx).get_schema()


# ---------------------------------------------------------------------------
# Tool 2: upload_data
# ---------------------------------------------------------------------------


@mcp.tool()
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


@mcp.tool()
async def list_uploads(
    limit: int = 50,
    offset: int = 0,
    name: str = "",
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """List datasets previously uploaded via the API (newest first).

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


@mcp.tool()
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


# ---------------------------------------------------------------------------
# Tool 3: list_models
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_models(
    include_unsaved: bool = False,
    limit: int = 50,
    offset: int = 0,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """List all Marketing Mix Models for the authenticated user.

    Returns model name, hash, status (pending/under way/complete/failed),
    type (mmm/var), hierarchy value, and timestamps.

    NOTE: All other model endpoints use model_hash (string, e.g. "f835671a25")
    as the identifier. Use the model_hash from this response.

    Args:
        include_unsaved: Include draft/unsaved models (default false).
        limit: Maximum number of models to return (default 50, max 500).
        offset: Number of models to skip, for paging past `limit` (default 0).
    """
    return await _client(ctx).list_models(
        include_unsaved=include_unsaved, limit=limit, offset=offset
    )


# ---------------------------------------------------------------------------
# Tool 4: create_model
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_model(
    uploaded_file_id: int,
    date_column: str,
    kpi_column: str,
    hierarchy_column: str,
    channels: list[dict],
    multiplier_column: str = "",
    control_columns: list[str] | None = None,
    total_media_effect: str = "Other",
    priors: list[dict] | None = None,
    trend: bool = False,
    seasonality: bool = False,
    likelihood: str = "normal",
    saturation_type: str = "tanh",
    transform_order: str = "adstock_first",
    link: str = "identity",
    channel_groups: list[dict] | None = None,
    control_reference: dict | None = None,
    name: str = "",
    operating_margin: float | None = None,
    operating_margin_column: str = "",
    attribution: str = "",
    annual_discount_rate: float | None = None,
    sampler: dict | None = None,
    reporting_kernel: dict | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Create and start fitting a new Bayesian Marketing Mix Model.

    This queues an async model fit and returns immediately with a model_hash.
    Use get_model_status to poll for progress until status is 'complete'.

    Priors are calculated automatically using smart defaults based on cost
    shares, industry benchmarks, and channel-type detection. You can
    override individual channels via the priors parameter.

    Args:
        uploaded_file_id: The file ID returned by upload_data.
        date_column: Name of the date column in the CSV.
        kpi_column: Name of the KPI/dependent variable column.
        hierarchy_column: Name of the brand/segment column (must have exactly 1 unique value).
        channels: List of channel definitions, each with keys: name, activity_column, spend_column.
                  Example: [{"name": "TV", "activity_column": "tv_grps", "spend_column": "tv_spend"}]
        multiplier_column: Column to convert KPI to revenue. Defaults to kpi_column.
        control_columns: Non-media control variable column names (e.g. ["price", "distribution"]).
        total_media_effect: Controls prior strength. Either an industry name for a benchmark
                           ("FMCG"=6%, "Retail"=9%, "TelCo"=30%, "Financial Services"=19%,
                           "E-Commerce"=22%, "Other"=12%) or a custom decimal like "0.15"
                           meaning "I believe all media drives 15% of my KPI". Default "Other".
        priors: Optional per-channel prior overrides. Each dict should have "channel" matching
                a channels[].name, plus any fields to override: distribution, mean, sd, lower,
                upper, transform, adstock_type, effect_period, alpha_sd (legacy),
                scalars (legacy), decay_lower/decay_upper (legacy — prefer the
                half_saturation_*/half_life_* fields described below).
                Only specified fields are overridden; the rest use smart defaults.
                Adstock-kernel fields: half_life_lower/half_life_upper (carryover half-life
                bounds in periods — preferred over the legacy decay_lower/decay_upper),
                theta_mean/theta_sd (peak-lag prior, adstock_type="delayed" only),
                dual_weight_mean/dual_weight_sd (long-term/slow-component share prior,
                adstock_type="dual_geometric" only). Saturation fields:
                sat_shape_mean/sat_shape_sd (curvature prior, saturation_type=
                "generalized_log" only; small values are near-logarithmic, 1.0 is
                michaelis_menten), half_saturation_mean/half_saturation_sd (the
                50%-of-maximum-response point in the channel's activity units —
                preferred over the legacy alpha_sd/scalars pair, and cannot be
                combined with it in the same override),
                half_marginal_mean/half_marginal_sd (generalized_log ONLY: the
                activity level where MARGINAL returns have halved. Use this
                rather than half_saturation_* at near-logarithmic curvature —
                the 50% point overflows below sat_shape_mean 0.00097657 and is
                rejected with a 400, while the half-marginal point is finite at
                every shape. Cannot be combined with the other two anchors;
                #632).
                UNKNOWN KEYS ARE REJECTED with a 400 naming the field
                (#630); they used to be dropped silently, fitting a
                hybrid of the override and the smart defaults. Common misses:
                "beta"/"beta_mean" -> mean, "beta_sd" -> sd, "sat_shape" ->
                sat_shape_mean. "name" and "parameter" are rejected too — they
                identify the smart-prior row the override merges onto.
        trend: Enable dynamic baseline trend component.
        seasonality: Enable automatic seasonality detection. The prior sigma on
                     the Fourier coefficients is chosen for the link (#534):
                     0.5 under link="log", 10 under "identity". The coefficients
                     live on the link's scale, so the additive default would
                     admit e^10x seasonal amplitude on a multiplicative model.
        likelihood: Likelihood function: "normal" (default), "lognormal", "logit",
                    "studentt", "poisson", "negativebinomial", or "quantile".
        saturation_type: Diminishing-returns curve family applied to media:
                         "tanh" (default), "michaelis_menten", "negative_exponential",
                         or "generalized_log" (two-parameter Box-Cox/power-log family
                         1 - (1+x/K)^(-shape); tune per channel via the
                         sat_shape_mean/sat_shape_sd prior fields).
        transform_order: "adstock_first" (default: carryover accumulates, then
                         saturates) or "saturation_first" (each period's spend
                         saturates, then the effect spreads over time through the
                         normalized adstock kernel).
        link: Model Form. "identity" (default) fits an additive model — components
              add on the outcome scale. "log" fits a multiplicative model —
              components add on the log scale and media effects are percentage
              lifts. Under the removal_lift attribution convention (the API
              default), contributions then include an Overlap reconciliation
              column; the other conventions (aumann_shapley, shapley,
              proportional_normalized — the dashboard default) allocate the
              interaction across components and close exactly WITHOUT an
              Overlap column (see get_model_results).
        channel_groups: Optional adstock groups: [{"name": ..., "channels":
                        [...], "share_saturation": bool}]. Member channels tie
                        their carryover parameters (decay/theta/dual-weight —
                        plus saturation when share_saturation is true) to one
                        shared value, e.g. grouping channels into shared
                        "Long"/"Short" carryover classes. Members are
                        channels[].name values; each group needs >= 2 members;
                        groups must be disjoint; and tied members must have
                        identical adstock_type/effect_period/bound overrides
                        (the API rejects divergent groups at request time).
        control_reference: Control attribution reference points (#452),
                        multiplicative models (link="log") only: maps control
                        column names (plus optional "_default") to
                        "auto" | "absent" | "average" | "lowest" | "highest" —
                        which counterfactual "remove this control" means in
                        the contributions. "absent" measures against the
                        variable at zero (legacy behavior; honest only when
                        zero is observed). "average"/"lowest"/"highest"
                        reference the control at its observed mean/min/max —
                        use for controls that never approach zero (price
                        indices, distribution levels), where a zero
                        counterfactual produces unbounded contributions and a
                        negative Base. "auto" detects per control whether
                        zero is inside the observed data range. Example:
                        {"_default": "auto", "relative_price": "average",
                        "promo_flag": "absent"}. Omit entirely to keep every
                        control at "absent" (byte-identical legacy output).
                        Unknown control names/modes are rejected at request
                        time; any value other than "absent" requires
                        link="log". The fit reports the resolution in
                        model_config.control_references (see
                        get_model_results).
        name: Display name for the created model, honoured verbatim (#575).
              Falls back to a generated API_MMM_{brand}_{hash} string when
              omitted. Either way the model starts unsaved — invisible to
              list_models unless include_unsaved=true — until save_model
              files it into a project.
        operating_margin: Scalar operating margin as a decimal fraction in
              (0, 1], e.g. 0.18 = 18%. Mutually exclusive with
              operating_margin_column (the API 400s when both are given).
              Storing a margin unlocks the `financials` results section and
              lets run_optimizer(objective="profit") use it automatically
              instead of requiring forward_margin on every call.
        operating_margin_column: Name of a column in the uploaded CSV holding
              a per-date margin series (each value a fraction in (0, 1]).
              Same unlocks as operating_margin; the column must exist in the
              uploaded file. CAUTION: the API reads the margin keys from the
              REQUEST ROOT — a margin placed inside a config dict is silently
              ignored (no error), and the model fits marginless.
        attribution: Attribution convention for the contribution decomposition,
              resolved at fit time: "removal_lift" (default; one-at-a-time
              removal — multiplicative models then emit the Overlap column),
              "proportional_normalized" (the dashboard default),
              "aumann_shapley", or "shapley". Any value other than
              "removal_lift" requires link="log" (the API rejects it on
              additive models). The non-removal conventions allocate the
              interaction across components and close exactly WITHOUT an
              Overlap column.
        annual_discount_rate: Annual discount rate (decimal >= 0, e.g. 0.08)
              used by the display-time financial bridge and cohort ledger PV
              discounting. Display-time only — does not change the fit.
        sampler: MCMC sampler overrides, e.g. {"n_samples": 2000,
              "tune": 1500, "chains": 4, "cores": 2, "target_accept": 0.95}.
              STRICTLY validated: unknown keys inside sampler are rejected
              with a 400 naming the field; cores must be 1-8. Only the keys
              you send are overridden.
        reporting_kernel: Cohort-horizon reporting override (#449/#450), e.g.
              {"mode": "complete"} or a per-channel spec. Channel names are
              validated against channels[].name / activity_column at request
              time. Affects reported decompositions, not the fit itself.

    Returns the model_hash for status polling.
    """
    payload: dict = {
        "data_source": {"uploaded_file_id": uploaded_file_id},
        "date_column": date_column,
        "kpi_column": kpi_column,
        "hierarchy_column": hierarchy_column,
        "channels": channels,
        "control_columns": control_columns or [],
        "total_media_effect": total_media_effect,
        "config": {
            "trend": trend,
            "seasonality": seasonality,
            "likelihood": likelihood,
        },
    }
    # Non-default architecture options only (keeps default payloads
    # byte-identical to pre-0.2 versions).
    if saturation_type != "tanh":
        payload["config"]["saturation_type"] = saturation_type
    if transform_order != "adstock_first":
        payload["config"]["transform_order"] = transform_order
    if link != "identity":
        payload["config"]["link"] = link
    if channel_groups:
        payload["config"]["channel_groups"] = channel_groups
    if control_reference:
        payload["config"]["control_reference"] = control_reference
    if attribution:
        payload["config"]["attribution"] = attribution
    if annual_discount_rate is not None:
        payload["config"]["annual_discount_rate"] = annual_discount_rate
    if sampler:
        payload["config"]["sampler"] = sampler
    if reporting_kernel:
        payload["config"]["reporting_kernel"] = reporting_kernel
    if multiplier_column:
        payload["multiplier_column"] = multiplier_column
    if priors:
        payload["priors"] = priors
    if name:
        payload["name"] = name
    # Margin keys are TOP-LEVEL request fields, not config: the API reads them
    # from the request root and silently ignores them inside config (#26).
    if operating_margin is not None:
        payload["operating_margin"] = operating_margin
    if operating_margin_column:
        payload["operating_margin_column"] = operating_margin_column

    return await _client(ctx).create_model(payload)


# ---------------------------------------------------------------------------
# Tool 4b: create_var_model / link_var_model / unlink_var_model
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_var_model(
    uploaded_file_id: int,
    date_column: str,
    endogenous_vars: list[str],
    exogenous_vars: list[str] | None = None,
    lags: int = 1,
    forecast_horizon: int = 12,
    base_variable: str | None = None,
    equity_variables: list[str] | None = None,
    lre_horizon: int | None = None,
    lre_ci: float | None = None,
    var_priors: dict | None = None,
    name: str = "",
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Create and start fitting a long-term (VAR) model (#569).

    VAR models capture the joint dynamics of several series (e.g. sales and
    brand-equity metrics) and produce the long-run elasticity bridge behind
    the MMM's `long_run_rollup` results section. Fit one, then link it to an
    MMM with link_var_model.

    Args:
        uploaded_file_id: Dataset id from upload_data (must contain every
            named column).
        date_column: Date column name. Cannot also be a series.
        endogenous_vars: At least two column names — the jointly-modeled
            series.
        exogenous_vars: Optional outside drivers; must not overlap the
            endogenous set.
        lags: VAR order (>= 1). The dataset needs at least lags + 10 rows
            with no missing values across the modeled columns.
        forecast_horizon: Periods forecast for diagnostics (default 12).
        base_variable: The outcome series (must be endogenous) long-run
            multipliers are measured against. Required for long-run effects.
        equity_variables: Endogenous columns (excluding the base) whose
            long-run IRF multipliers are estimated. Required for long-run
            effects.
        lre_horizon: Long-run effects horizon in periods (default 156).
        lre_ci: Credible-interval mass for the effects table, in (0, 1).
        var_priors: Advanced prior overrides (lag_coefs / alpha / coefs /
            noise_chol); unknown keys are rejected.
        name: Display name for the created model, honoured verbatim (#575).
            Falls back to a generated API_VAR_* string when omitted.

    Returns 202-style payload with model_hash; poll get_model_status.
    """
    config: dict = {
        "endogenous_vars": endogenous_vars,
        "lags": lags,
        "forecast_horizon": forecast_horizon,
    }
    if exogenous_vars:
        config["exogenous_vars"] = exogenous_vars
    if base_variable:
        config["base_variable"] = base_variable
    if equity_variables:
        config["equity_variables"] = equity_variables
    if lre_horizon is not None:
        config["lre_horizon"] = lre_horizon
    if lre_ci is not None:
        config["lre_ci"] = lre_ci
    if var_priors:
        config["var_priors"] = var_priors

    payload = {
        "model_type": "var",
        "data_source": {"uploaded_file_id": uploaded_file_id},
        "date_column": date_column,
        "config": config,
    }
    if name:
        payload["name"] = name
    return await _client(ctx).create_model(payload)


@mcp.tool()
async def link_var_model(
    model_hash: str,
    var_model_hash: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Link a completed VAR model to an MMM (#569).

    After linking, the MMM's get_model_results `long_run_rollup` section
    joins the VAR's long-run elasticities with the MMM's short-term revenue.
    A VAR links to at most one MMM at a time — the error names the current
    owner if it is already linked elsewhere.

    Args:
        model_hash: The MMM to attach the long-run view to.
        var_model_hash: The VAR model (from create_var_model).
    """
    return await _client(ctx).link_var_model(model_hash, var_model_hash)


@mcp.tool()
async def unlink_var_model(
    model_hash: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Remove an MMM's VAR link (#569). Idempotent."""
    return await _client(ctx).unlink_var_model(model_hash)


# ---------------------------------------------------------------------------
# Tool 4c: contribution groups (set/get)
# ---------------------------------------------------------------------------


@mcp.tool()
async def set_contribution_groups(
    model_hash: str,
    contribution_groups: list[dict],
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Persist the driver groupings the dashboard contributions view renders
    (#436) — configure grouping once and every viewer sees it.

    Each group: {"name": str, "drivers": [column names], "color": "#hex"?,
    "baseAdjustments": {driver: "min"|"max"|"none"}?}. Driver names are
    validated against the model's media/control/halo/trademark factors
    (400 with a did-you-mean hint on typos); each driver may belong to at
    most one group; baseAdjustments must reference the group's own drivers.
    The special "_channel_color_overrides" pseudo-group carries a
    channelColors map instead of drivers.

    NOTE: this is the CONTRIBUTIONS-VIEW grouping. create_model's
    channel_groups is the unrelated adstock parameter-sharing feature —
    do not confuse them.
    """
    return await _client(ctx).put_contribution_groups(model_hash, contribution_groups)


@mcp.tool()
async def get_contribution_groups(
    model_hash: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Read the stored contribution groups for a model (#436).
    Legacy dashboard-saved configs are served verbatim."""
    return await _client(ctx).get_contribution_groups(model_hash)


# ---------------------------------------------------------------------------
# Tool 5: get_model_status
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Model curation (#575): rename_model / save_model
# ---------------------------------------------------------------------------


@mcp.tool()
async def rename_model(
    model_hash: str,
    name: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Rename a model.

    Changes only the display name; the model's saved/unsaved state is
    untouched (use save_model to file it into a project). The name is
    HTML-sanitized server-side and must be non-empty.

    Args:
        model_hash: Hash of the model to rename.
        name: New display name.
    """
    return await _client(ctx).rename_model(model_hash, name)


@mcp.tool()
async def save_model(
    model_hash: str,
    name: str,
    project_id: int | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Save a model into a project under a display name.

    API-created models start unsaved and are invisible to list_models
    (without include_unsaved=true) — saving files them into a project so
    they appear in the default listing and the dashboard's Saved Models.

    The same saved-models cap applies as in the dashboard: at the cap the
    API returns a 400 with error_type "saved_limit". Re-saving an
    already-saved model renames/refiles it without consuming a new slot.

    Args:
        model_hash: Hash of the model to save.
        name: Display name to save under (non-empty).
        project_id: Optional target project ID; must be a project you own
            or one shared with a team you belong to. Defaults to your
            default project.
    """
    return await _client(ctx).save_model(model_hash, name, project_id=project_id)


@mcp.tool()
async def get_model(
    model_hash: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Get a model's metadata and configuration echo — works for EVERY status,
    including failed models (unlike get_model_results, which needs 'complete').

    Use this to inspect what a model was configured with, why it failed, or
    where it lives. Returns: id, model_hash, name, status, model_type
    ("mmm"/"var"), hierarchy_value, periodicity, is_saved, project_id/name,
    linked_var_model_hash, created_at/completed_at, error (the failure
    message — non-null only when status is "failed"), and model_config (the
    create-time configuration echo: data_source, columns, channels, priors
    as resolved, and the config flags).

    NOTE: the echo omits a few accepted create_model inputs
    (operating_margin, annual_discount_rate, reporting_kernel) — absence
    there does not mean they weren't applied; check the financials results
    section for the stored margin.

    Args:
        model_hash: The model hash (any status).
    """
    return await _client(ctx).get_model(model_hash)


@mcp.tool()
async def delete_model(
    model_hash: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """PERMANENTLY DELETE a FAILED model. Destructive and irreversible.

    Only models with status "failed" can be deleted over the API — any other
    status returns a 409 with the model's current status (delete is for
    cleaning up failed fits, not curating good ones). Deleting also unlinks
    any MMMs that pointed at it as their VAR model and removes stored
    artifacts. On success returns {"deleted_model_hash": ..., "status":
    "deleted"}.

    Check first with get_model or get_model_status if unsure of the status.

    Args:
        model_hash: Hash of the FAILED model to delete permanently.
    """
    return await _client(ctx).delete_model(model_hash)


@mcp.tool()
async def get_model_status(
    model_hash: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Check the fitting progress of a model.

    Returns status (pending/under way/complete/failed), progress percentage,
    estimated time remaining, and timestamps.

    Args:
        model_hash: The model hash returned by create_model or list_models.
    """
    return await _client(ctx).get_model_status(model_hash)


# ---------------------------------------------------------------------------
# Tool 6: get_model_results
# ---------------------------------------------------------------------------


_CURVE_SECTIONS = ("response_curves", "marginal_curves")
_BAND_SUFFIXES = ("_lower_50", "_upper_50", "_lower", "_upper")


def _norm_channel(name: str) -> str:
    """Normalize a channel identifier for matching: lowercase, spaces to
    underscores, and strip the _activity/_spend suffix (results are keyed by
    activity-column name)."""
    k = str(name).strip().lower().replace(" ", "_")
    for suffix in ("_activity", "_spend"):
        if k.endswith(suffix):
            k = k[: -len(suffix)]
            break
    return k


def _column_channel(col: str) -> str:
    """Base channel of a curve column, with any credible-band suffix removed."""
    for suffix in _BAND_SUFFIXES:
        if col.endswith(suffix):
            col = col[: -len(suffix)]
            break
    return _norm_channel(col)


def _downsample(records: list, max_points: int) -> list:
    """Stride a grid-record list down to <= max_points, keeping first and last."""
    n = len(records)
    if max_points < 2 or n <= max_points:
        return records
    idx = {round(i * (n - 1) / (max_points - 1)) for i in range(max_points)}
    return [records[i] for i in sorted(idx)]


def _filter_results(payload: dict, channels: list | None, max_grid_points: int | None) -> dict:
    """Client-side channel filter + curve downsampling on a results payload.

    Applies only where channel identity is unambiguous. `contributions` is
    passed through untouched: its non-channel columns (controls, Base,
    Seasonality, ...) cannot be reliably told apart from unrequested channels.
    """
    target = payload.get("results") if isinstance(payload.get("results"), dict) else payload
    wanted = {_norm_channel(c) for c in channels} if channels else None

    for section in _CURVE_SECTIONS:
        recs = target.get(section)
        if not isinstance(recs, list):
            continue
        if wanted is not None:
            recs = [
                {k: v for k, v in r.items() if k == "Spend" or _column_channel(k) in wanted}
                for r in recs
            ]
        if max_grid_points:
            recs = _downsample(recs, max_grid_points)
        target[section] = recs

    if wanted is not None:
        for section in ("decay_curves", "saturation"):
            entry = target.get(section)
            sub = (
                entry.get("channels")
                if section == "saturation" and isinstance(entry, dict)
                else entry
            )
            if isinstance(sub, dict):
                filtered = {k: v for k, v in sub.items() if _norm_channel(k) in wanted}
                if section == "saturation":
                    entry["channels"] = filtered
                else:
                    target[section] = filtered
        for section, key in (("channel_summary", "Channel"), ("coefficients", "Channel")):
            recs = target.get(section)
            if isinstance(recs, list):
                target[section] = [r for r in recs if _norm_channel(r.get(key, "")) in wanted]
        mroi = target.get("mroi_summary")
        if isinstance(mroi, dict) and isinstance(mroi.get("channels"), list):
            mroi["channels"] = [
                r for r in mroi["channels"] if _norm_channel(r.get("channel", "")) in wanted
            ]
        # Per-period series (#591): channels x periods rows — the largest
        # per-channel section, so the filter matters most here.
        periods = target.get("mroi_periods")
        if isinstance(periods, dict) and isinstance(periods.get("rows"), list):
            periods["rows"] = [
                r for r in periods["rows"] if _norm_channel(r.get("channel", "")) in wanted
            ]
    return payload


@mcp.tool()
async def get_model_results(
    model_hash: str,
    sections: str = "",
    format: str = "json",
    channels: list[str] | None = None,
    max_grid_points: int | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Get results from a completed model.

    Available sections:
    - channel_summary: per-channel aggregates {Channel, Sales, Spend, Revenue, ROI}.
    - contributions: per-period decomposition (Date, one column per channel, plus
      Base, Seasonality, Event Effect, Model, Fit Actual, Actual). Values are in
      KPI/unit space — the multiplier is NOT applied. Use `coefficients` for
      per-period revenue. Multiplicative (link="log") models fitted with the
      removal_lift attribution convention add an `Overlap` column: a negative
      shared-synergy reconciliation term so that
      Base + components + Overlap = Model. Overlap is NOT a channel — never
      rank it, share it, or feed it to the optimizer/scenarios. Overlap
      requires BOTH link="log" AND attribution="removal_lift" (the API
      default): under aumann_shapley, shapley, or proportional_normalized
      (the dashboard default) the interaction is allocated across components,
      which close exactly with NO Overlap column — its absence does NOT mean
      the model is additive or predates the feature.
      Control columns are measured against the reference point resolved at
      fit time (#452, see model_config.control_references) — e.g. "vs.
      average conditions" for a control that never reaches zero — not
      necessarily against zero, so a referenced control's series
      legitimately spans zero.
    - coefficients: per-period per-channel media results table (Date, Channel,
      Sales, Revenue, Spend, Media Units, ROI, Cost/Revenue/Sales per Media Unit).
      This is the only per-period revenue-space decomposition.
    - params: fitted posterior means per channel (alpha, decay, cpu, scalars).
    - decay_curves: adstock decay per channel (mean/lower/upper, l_max,
      adstock_type, curve points; dual-geometric models add decay_slow_* and
      dual_weight_* parameters).
    - response_curves: 100-point spend-vs-revenue grid per channel with credible
      bands ({ch}, {ch}_lower, {ch}_lower_50, {ch}_upper_50, {ch}_upper).
    - marginal_curves: same grid for marginal ROI (diminishing returns).
    - saturation: fitted saturation family and parameters (saturation_type is
      tanh, michaelis_menten, negative_exponential, or generalized_log;
      per-channel alpha/scale, plus transform_order and — for generalized_log
      only — per-channel sat_shape).
    - mroi_summary: headline marginal ROI at current spend per channel with a
      94% HDI (channel, current_spend, mroi_median, mroi_hdi_3, mroi_hdi_97).
      Post-#591 posterior fits add two averaging-convention scalars per
      channel — mroi_allperiods_unweighted_median (+_hdi_3/_hdi_97) and
      mroi_spendweighted_active_median (+_hdi_3/_hdi_97), with *_profit_*
      variants on margin models — plus a top-level conventions_available
      array. Channels with no active periods omit the spendweighted fields.
      Post-#629 fits also carry a *_mean beside every *_median (mroi_mean,
      mroi_profit_mean, pv_kernel_mass_mean, and the convention variants).
      The median is what the product displays; the mean is the statistic that
      reconciles with the marginal-revenue curve, since derivative and mean
      commute and median does not. Absent on anything fitted before #629 —
      there is no backfill, so feature-detect rather than assume.
    - mroi_periods: OPT-IN ONLY (#591) — never in the default payload;
      request it by name in `sections`. Per-period marginal ROI series:
      {available, hdi_prob, evaluation_point: "historical_period_spend",
      rows} with one row per (channel x modelled period): channel, date,
      spend, mroi_median/_hdi_3/_hdi_97, and mroi_profit_* on margin models.
      Models fitted before the artifact existed return
      {available: false, reason: "fitted_before_mroi_periods"} — refit to
      enable. Large (channels x periods) — pair with the channels filter.
    - model_stats: fit diagnostics (R², MAPE, Durbin-Watson, Max R_hat, ...).
    - actual_vs_model: actual vs predicted per period with 50%/95% HDIs.
    - long_run_rollup: MMM short-term + VAR long-run revenue rollup per channel;
      returns {available: false, reason: "no_linked_var_model"} when no VAR
      model is linked to this MMM.
    - optimizer: latest optimization results (see get_optimizer_results).
    - predictions: latest scenario prediction rows (see get_scenario_results).
    - posterior: full posterior summary table — one row per model variable
      with mean, sd, hdi_3%, hdi_97%, and r_hat (quotable 94% HDIs and
      per-variable convergence).
    - posterior_transforms: the importable transform-parameter posterior grid
      (what the dashboard's prior builder imports): per-channel alpha mean/sd,
      decay 94% HDI, dual-weight mean/sd, decay-slow HDI, sat-shape mean/sd,
      and the adstock structure including tied-group member aliases. Rows key
      on activity-column names — join via channel_map.
    - r_hat: per-parameter R-hat over ALL posterior variables — including
      transform RVs such as {channel}_decay that the posterior summary's
      coefficient rows do not cover. Use it to attribute a bad Max R_hat
      (model_stats) to a specific parameter block.
    - financials: the model's operating margin ({operating_margin,
      operating_margin_series}); omitted entirely for marginless models.
      operating_margin_series is a DATE-STRING-KEYED DICT
      ({"2024-01-01": 0.18, ...}), not a list of records.
    - cohort_ledger: per-(channel, source-period) forward-allocation ledger —
      each period's spend is credited with the future effects its adstock
      carryover earns (horizon slices plus PV-discounted financials from the
      fit-time cohort kernels). Models fitted before the artifact existed
      return {available: false, reason: ...} — feature-detect on `available`.
    - model_config: the resolved model specification (inputs, not posteriors)
      to audit or reconstruct the create_model call — includes config flags
      such as saturation_type, transform_order, and link ("log" =
      multiplicative). Multiplicative models with controls also report
      control_references (#452): per control, the requested and resolved
      attribution reference mode, the zero_distance diagnostic behind the
      "auto" choice, and the posterior-mean q_ref. Models created before
      these fields existed may omit them.
    - channel_map: canonical identifier mapping, one record per channel:
      {channel, activity_column, spend_column} as configured at create time.
      This is the join key between channels[].name and the sections keyed by
      activity-column name (contributions, decay_curves, posterior_transforms).

    The response envelope includes `sections_available` — trust it over any
    hardcoded list if the server is newer than these docs.

    IMPORTANT — channel naming: results are keyed by the channel's ACTIVITY
    COLUMN name (e.g. "search_activity"), not by the `channels[].name` passed to
    create_model. These exact keys (case- and space-sensitive) must be used in
    run_optimizer bounds, laydown_weights, and period_cpm. Always read
    channel_summary first to get the exact keys.

    NOTE: Date values in contributions/coefficients records are millisecond
    epoch integers.

    CONTEXT-SIZE TIP: a full pull is very large (curve sections alone are 100
    grid points x channels x 5 band columns). In conversational use, request
    only the sections you need and pass channels=[...] and max_grid_points=20.

    Args:
        model_hash: The model hash.
        sections: Comma-separated list of sections to include.
                  Leave empty for all sections.
                  Common: "channel_summary,model_stats" for ROI and diagnostics.
        format: "json" (default) or "csv". CSV returns
                {"format": "csv", "content": "..."} — concatenated
                "# section" + CSV blocks, useful for saving to disk.
                Filtering below applies to JSON only.
        channels: Optional channel filter (matching is case/space-insensitive
                  and tolerates the _activity/_spend suffix). Applied to curve
                  sections, decay_curves, saturation, channel_summary,
                  coefficients, mroi_summary, and mroi_periods rows.
                  `contributions` is never filtered (its control columns are
                  indistinguishable from channels client-side).
        max_grid_points: Optional cap on response/marginal curve grid points;
                         records are strided evenly, keeping first and last.
    """
    res = await _client(ctx).get_model_results(model_hash, sections=sections, fmt=format)
    if format != "json" or (channels is None and max_grid_points is None):
        return res
    if not isinstance(res, dict) or res.get("_status_code", 200) >= 400:
        return res
    return _filter_results(res, channels, max_grid_points)


# ---------------------------------------------------------------------------
# Tool 7: run_optimizer
# ---------------------------------------------------------------------------


@mcp.tool()
async def run_optimizer(
    model_hash: str,
    total_budget: float,
    num_periods: int,
    gamma: float,
    currency: str,
    bounds: dict,
    laydown_weights: dict,
    period_cpm: dict,
    objective: str = "revenue",
    forward_margin: float | None = None,
    period_multiplier: list[float] | None = None,
    include_historical_effect: bool = True,
    enable_warm_start: bool = True,
    optimizer_engine: str = "slsqp",
    sigma_penalty: str = "std",
    group_bounds: list[dict] | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Run budget optimization on a completed model.

    Finds the optimal budget allocation across channels to maximize
    predicted revenue — or predicted PROFIT with objective="profit" —
    within the given constraints.

    PROFIT OBJECTIVE: objective="profit" requires a margin source. If the model
    was built with an operating margin, it is used automatically; otherwise you
    MUST pass forward_margin (e.g. 0.18 for an 18% margin) or the API returns an
    error. Result fields (Revenue, ROI, ExpectedResponse) are then on the profit
    basis.

    IMPORTANT:
    - Channel names must exactly match model results (case-sensitive, space-sensitive).
      Results are keyed by the channel's ACTIVITY COLUMN name (e.g. "search_activity"),
      not by the `channels[].name` passed to create_model.
      Call get_model_results with sections="channel_summary" first to get exact names,
      or use get_scenario_template to discover channel names and their average CPM values.
    - bounds values are percentages of total_budget (0-100), not currency amounts.
    - laydown_weights and period_cpm must be ARRAYS of length num_periods, not scalars.
      Wrong: {"TV": 10}. Correct: {"TV": [10, 10, 10, 10]}.
    - The same channel keys must appear in all three: bounds, laydown_weights, and period_cpm.
    - All period_cpm values must be positive (> 0).
    - laydown_weights per channel must sum to a positive value (weights are normalized internally).

    Returns 202 (async). Use get_optimizer_results to poll until status is "complete".

    Args:
        model_hash: Hash of a completed model.
        total_budget: Total budget in currency units.
        num_periods: Number of periods to optimize over (matches your planning horizon).
        gamma: Uncertainty-aversion weight on the outcome spread (the
               objective is mean - gamma * spread). 0.0 = maximize expected
               return only (most aggressive); higher values penalize
               uncertainty harder (more conservative). The dashboard
               typically uses values in the 0-0.1 range.
        currency: Currency code (e.g. "USD", "GBP").
        bounds: Per-channel min/max budget allocation as PERCENTAGES (0-100).
                Every channel must appear. Example:
                {"TV_Impressions": {"lower": 5, "upper": 40},
                 "Search_Clicks": {"lower": 10, "upper": 50}}
        laydown_weights: Per-channel spend timing weights. Each value is an array of
                        length num_periods. Weights are relative (normalized internally).
                        Use uniform [1, 1, ...] for even distribution across periods.
                        Example: {"TV_Impressions": [1, 1, 1, 1]}
        period_cpm: Per-channel cost-per-metric for each period. Each value is an array
                   of length num_periods with positive values. Get baseline CPM from
                   get_scenario_template (avg_cpu_by_channel field).
                   Example: {"TV_Impressions": [10.5, 10.5, 10.5, 10.5]}
        objective: "revenue" (default) or "profit". See PROFIT OBJECTIVE above.
        forward_margin: Decimal margin in (0, 1], e.g. 0.18 = 18%. Only used with
                       objective="profit"; required when the model has no stored
                       operating margin.
        period_multiplier: Optional array of length num_periods converting KPI
                          units to revenue per period over the planning horizon
                          (mirrors the model's multiplier_column, e.g. price).
        include_historical_effect: Include carryover from historical spend in the
                                  predicted response (default True).
        enable_warm_start: Warm-start the optimizer from a previous solution
                          (default True).
        optimizer_engine: "slsqp" (hardened SLSQP, default) or "marginal"
                         (water-fill engine: allocates until every funded
                         channel shows the same marginal return; exact
                         profit-hurdle semantics and the tightest optimality
                         certificates, with automatic SLSQP fallback).
        sigma_penalty: How gamma penalizes outcome spread: "std" (default),
                      "variance" or "frozen" (advanced; smoother alternatives
                      for hard-to-converge runs - leave on "std" normally).
        group_bounds: Joint constraints over channel SETS (#570),
                     e.g. [{"name": "trade", "channels": ["TV", "Search"],
                     "lower": 40, "upper": 60}] with lower/upper in % of
                     total_budget (same convention as bounds). Groups must be
                     disjoint and jointly feasible with the members'
                     per-channel bounds. Presence forces the slsqp engine.
                     Results gain GroupBounds/GroupBoundsReport columns; a
                     BINDING group's members legitimately sit off the global
                     marginal (they share the group's shadow price).
    """
    payload = {
        "total_budget": total_budget,
        "num_periods": num_periods,
        "gamma": gamma,
        "currency": currency,
        "bounds": bounds,
        "laydown_weights": laydown_weights,
        "period_cpm": period_cpm,
    }
    if objective != "revenue":
        payload["objective"] = objective
    if forward_margin is not None:
        payload["forward_margin"] = forward_margin
    if period_multiplier is not None:
        payload["period_multiplier"] = period_multiplier
    if not include_historical_effect:
        payload["include_historical_effect"] = False
    if not enable_warm_start:
        payload["enable_warm_start"] = False
    if group_bounds:
        # #570: additive-only, same hash-preservation rule as engine/penalty.
        payload["group_bounds"] = group_bounds
    # Engine + penalty (#502): additive-only so default payloads stay
    # byte-identical (server-side content-hash dedup stays valid).
    if optimizer_engine != "slsqp":
        payload["optimizer_engine"] = optimizer_engine
    if sigma_penalty != "std":
        payload["sigma_penalty"] = sigma_penalty
    return await _client(ctx).run_optimizer(model_hash, payload)


# ---------------------------------------------------------------------------
# Tool 8: get_optimizer_results
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_optimizer_results(
    model_hash: str,
    run_id: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Get budget optimization status and results.

    Without run_id: returns the MODEL-LEVEL optimizer state. Top-level keys:
    `optimizer_status` ("none"/"pending"/"under way"/"complete"/"failed"),
    `progress` + `progress_text` while running, and `results` when complete.
    This reflects the LATEST run on the model — a newer run overwrites it, so
    a poller can lose sight of the run it submitted.

    With run_id (run_optimizer's response includes it): fetches that specific
    run, immune to later runs. Top-level keys include `run_id`, `model_hash`,
    `status`, `created_at`, `label`, `inputs`, and `results`. Poll THIS form
    when you need to know whether your own run completed.

    Reading `results` rows — the columns come from DIFFERENT conventions and
    must not be treated as interchangeable:
    - `Revenue` / `ROI`: the optimizer's DECISION math — removal-lift
      counterfactual revenue at the allocated spend. This is what the solver
      optimized.
    - `OptimizedEvalRevenue` / `OptimizedEvalROI` and `HistoricalRevenue` /
      `HistoricalROI`: fitted-convention COMPARISON columns — the reconciled
      accounting view matching the model's Contributions panel. Same spend,
      different question; never mix them with `Revenue`/`ROI` in one summary.
    - `ObjectiveMarginal`: the decision-math marginal return at the optimum
      (the quantity the solver equalizes across unconstrained channels).
    - `MroiAtOptimized` / `MroiAtOptimizedHdi3` / `MroiAtOptimizedHdi97`:
      posterior mROI evaluated at the optimized spend (94% HDI bounds) — a
      DIFFERENT quantity from ObjectiveMarginal (they can differ by several
      times); quote the one matching the question asked.
    - Convergence / KKT certificate fields report solver health. All-None
      placeholder arrays (PeriodResponse etc.) are stripped server-side.

    Args:
        model_hash: Hash of the model that was optimized.
        run_id: Optional optimization run id from run_optimizer's response.
            Pass it to poll a specific run's status/results.
    """
    return await _client(ctx).get_optimizer_results(model_hash, run_id=run_id)


# ---------------------------------------------------------------------------
# Tool 9: get_scenario_template
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_scenario_template(
    model_hash: str,
    periods_forward: int = 12,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Generate a forward-period scenario template from a completed model.

    Returns future dates pre-filled with values from 1 year prior,
    the list of media and control channels, and average cost-per-unit
    per media channel.

    IMPORTANT: Always call this before run_scenario or run_optimizer to discover:
    - Channel names (use these exact names in scenario_data, bounds, laydown_weights, period_cpm)
    - Average CPM per channel (avg_cpu_by_channel — use for period_cpm in run_optimizer)
    - Baseline activity values per channel (rows — use as starting point for scenarios)
    - Media vs control channel classification (variable_classification field)

    The response also includes: operating_margin (the model's stored margin, if
    set — useful for profit math), variable_transforms (per-variable transform
    metadata), periodicity, and start_date.

    WARNING: Template data may contain NaN or null values for channels without
    historical data. You MUST replace NaN/null with 0 before passing to run_scenario,
    otherwise the prediction will fail downstream.

    Args:
        model_hash: Hash of a completed model.
        periods_forward: Number of future periods to generate (default 12).
    """
    return await _client(ctx).get_scenario_template(model_hash, periods_forward)


# ---------------------------------------------------------------------------
# Tool 10: run_scenario
# ---------------------------------------------------------------------------


@mcp.tool()
async def run_scenario(
    model_hash: str,
    scenario_data: list[dict],
    spend_metadata: list[dict] | None = None,
    rebuild_model: bool = True,
    evaluate_holdout: bool = False,
    skip_slicing: bool = False,
    proxy_channels: list[dict] | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Run a "what-if" scenario prediction on a completed model.

    Takes a set of future period rows with channel activity values and
    predicts the KPI outcome. Use get_scenario_template first to get
    the expected format, channel names, and baseline values. Channel names are
    the activity-column keys from the template/results (e.g. "search_activity"),
    not the `channels[].name` passed to create_model.

    IMPORTANT: Before submitting, replace any NaN/null values in scenario_data with 0.
    The template from get_scenario_template may contain NaN for channels without
    historical data, which will cause the prediction to fail.

    This is async (returns 202 with status "pending"). Poll get_scenario_results
    until status is "complete" or "failed".

    Workflow: get_scenario_template -> modify values -> run_scenario -> poll get_scenario_results

    Args:
        model_hash: Hash of a completed model.
        scenario_data: Array of period rows, each a dict with "Date" (YYYY-MM-DD format)
                      and channel activity columns. Channel names must match exactly what
                      get_scenario_template returns in the "channels" field.
                      Example: [{"Date": "2025-01-06", "TV_Impressions": 50000, "Search_Clicks": 1200}]
        spend_metadata: Optional per-channel spend info for ROI calculation in results.
                       Each entry: {"channel": "TV_Impressions", "metric": "impressions",
                       "cpm": 25.0, "total_spend": 125000,
                       "weekly_spend": [25000, 25000, ...]}
        rebuild_model: Recompile the model graph before prediction. Must be True (default)
                      for API-initiated scenarios where the model graph is not in memory.
        evaluate_holdout: Evaluate the scenario against held-out actuals when the
                         scenario period overlaps observed data (default False).
        skip_slicing: Skip per-channel contribution slicing in the prediction
                     output — faster when only the KPI total is needed (default False).
        proxy_channels: Optional list of proxy-channel mappings, each mapping a
                       scenario channel to a fitted channel whose transforms it
                       borrows (for channels without their own history).
    """
    payload: dict = {"scenario_data": scenario_data}
    if spend_metadata:
        payload["spend_metadata"] = spend_metadata
    if rebuild_model:
        payload["rebuild_model"] = True
    if evaluate_holdout:
        payload["evaluate_holdout"] = True
    if skip_slicing:
        payload["skip_slicing"] = True
    if proxy_channels:
        payload["proxy_channels"] = proxy_channels
    return await _client(ctx).run_scenario(model_hash, payload)


# ---------------------------------------------------------------------------
# Tool 11: get_scenario_results
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_scenario_results(
    model_hash: str,
    run_id: str | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Get scenario prediction results.

    Without run_id: returns the MODEL-LEVEL scenario state — status
    (pending/complete/failed) and, when complete, the full prediction data
    including predicted KPI per period, channel contributions, confidence
    intervals, and base components (intercept, seasonality, trend). This
    reflects the LATEST scenario on the model — a newer run overwrites it,
    so a poller can lose sight of the run it submitted.

    With run_id (run_scenario's response includes it): fetches that specific
    saved run, immune to later runs — keys include `run_id`, `model_hash`,
    `name`, `status`, `pinned`, `notes`, `tags`, `key_metrics`, timestamps,
    `inputs` (the submitted payload), and `results`. Poll THIS form when you
    need to know whether your own run completed, or to disambiguate
    back-to-back scenarios.

    NOTE: Failed scenarios return status "failed" with an error message in the
    JSON body (not an HTTP error). Always check the status field.

    Args:
        model_hash: Hash of the model the scenario was run on.
        run_id: Optional scenario run id ("scn_..."), from run_scenario's
            response or list_runs(artifact="scenario").
    """
    return await _client(ctx).get_scenario_results(model_hash, run_id=run_id)


# ---------------------------------------------------------------------------
# Saved-run curation (#576): update_run / set_run_pinned
# ---------------------------------------------------------------------------


@mcp.tool()
async def update_run(
    artifact: str,
    model_hash: str,
    run_id: str,
    name: str = "",
    notes: str | None = None,
    tags: list[str] | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Rename / annotate a saved optimizer or scenario run.

    Runs are auto-named at creation (e.g. "$1.2M · 12mo · Jan 5");
    renaming makes run history carry the analysis ("holiday cut -10%",
    "stretch 130%"). Renaming permanently flips the run's auto_named flag
    to false so future auto-naming never overwrites it. Only the fields
    you provide are changed.

    Args:
        artifact: "optimizer" (run_id "opt_...") or "scenario" ("scn_...").
        model_hash: Hash of the model the run belongs to.
        run_id: The run's stable id from run history.
        name: New display name (non-empty when given; capped at 255 chars).
        notes: Free-text annotation. Omit to leave untouched; pass "" to
            clear.
        tags: Replacement tag list (max 20 tags, 64 chars each).
    """
    kwargs: dict = {}
    if name:
        kwargs["name"] = name
    if notes is not None:
        kwargs["notes"] = notes
    if tags is not None:
        kwargs["tags"] = tags
    return await _client(ctx).update_run(artifact, model_hash, run_id, **kwargs)


@mcp.tool()
async def set_run_pinned(
    artifact: str,
    model_hash: str,
    run_id: str,
    pinned: bool,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Pin or unpin a saved optimizer or scenario run.

    Declarative and idempotent: setting the current state again is a
    no-op, so scripts can safely re-run it.

    Args:
        artifact: "optimizer" (run_id "opt_...") or "scenario" ("scn_...").
        model_hash: Hash of the model the run belongs to.
        run_id: The run's stable id from run history.
        pinned: Desired pin state.
    """
    return await _client(ctx).set_run_pinned(artifact, model_hash, run_id, pinned)


@mcp.tool()
async def list_runs(
    artifact: str,
    model_hash: str,
    limit: int = 50,
    offset: int = 0,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """List a model's saved optimizer or scenario run history.

    Returns {model_hash, runs, count, limit, offset}. Each run summary has:
    run_id, name, auto_named, pinned, notes, tags, status, error_details,
    progress fields while running, key_metrics (optimizer: total_budget,
    num_periods, gamma, predicted_revenue/roi, ...; scenario: num_periods,
    total_planned_spend, predicted_outcome, ...; null metrics are omitted —
    treat every key as optional), and created/started/completed timestamps.
    Ordering is pinned-first, then newest-first.

    CAVEATS:
    - `count` is the LENGTH OF THIS PAGE, not the total run count — page
      until a short page.
    - The optimizer objective ("revenue"/"profit") is NOT in the summary;
      fetch the specific run (get_optimizer_results with run_id) and read
      its `inputs` — profit runs carry `objective: "profit"` there, revenue
      runs omit the key.

    Use get_optimizer_results / get_scenario_results with a run_id to fetch
    a listed run's full inputs and results; update_run / set_run_pinned to
    curate it.

    Args:
        artifact: "optimizer" (run ids "opt_...") or "scenario" ("scn_...").
        model_hash: Hash of the model whose run history to list.
        limit: Page size (API clamps to 1-200; default 50).
        offset: Rows to skip (paging).
    """
    return await _client(ctx).list_runs(artifact, model_hash, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# ASGI app for uvicorn deployment (lazy to avoid overhead in stdio mode)
# ---------------------------------------------------------------------------


def _create_app():
    """Create the ASGI app for uvicorn/Streamable HTTP deployment."""
    set_http_mode(True)
    # host="0.0.0.0" opts out of the SDK's auto-enabled DNS-rebinding
    # protection (it activates when host is localhost-ish): this app runs
    # behind a reverse proxy with a public Host header, which the localhost
    # allowlist would reject.
    return mcp.streamable_http_app(
        streamable_http_path="/",
        json_response=True,
        stateless_http=True,
        host="0.0.0.0",
    )


def __getattr__(name: str):
    """Lazy module-level attribute access to avoid creating the HTTP app in stdio mode."""
    if name == "app":
        global app
        app = _create_app()
        return app
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
