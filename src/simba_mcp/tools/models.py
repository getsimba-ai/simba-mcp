"""Models tools backed by the shared Simba API."""

from typing import Any

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError

from ..auth import _client
from ..runtime import AppContext
from ..schemas import APIResult, Channel, ControlPrior


async def list_models(
    include_unsaved: bool = False,
    limit: int = 50,
    offset: int = 0,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
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


async def create_model(
    uploaded_file_id: int,
    date_column: str,
    kpi_column: str,
    hierarchy_column: str,
    channels: list[Channel],
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
    control_priors: list[ControlPrior] | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
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
                upper, transform, adstock_type, effect_period.
                Only specified fields are overridden; the rest use smart defaults.
                Adstock-kernel fields: half_life_lower/half_life_upper (carryover half-life
                bounds in periods — preferred over the legacy decay_lower/decay_upper),
                theta_mean/theta_sd (peak-lag prior, adstock_type="delayed" only),
                dual_weight_mean/dual_weight_sd (long-term/slow-component share prior,
                adstock_type="dual_geometric" only).
                SATURATION ANCHOR — state it ONCE, in exactly one of three
                mutually exclusive forms (two in one override -> 400 "state
                the saturation prior once"):
                (1) half_marginal_mean/half_marginal_sd — CANONICAL for
                saturation_type="generalized_log" (rejected on other
                families): the activity level where MARGINAL returns have
                halved, finite at every curvature (#632).
                sat_shape_mean MUST accompany the pair in the same override
                (#672) — the fold pairs your coefficient with the
                stated curvature, so omitting it is a 400, never a silent
                default.
                (2) half_saturation_mean/half_saturation_sd — the
                50%-of-maximum point in activity units, for the
                single-parameter families (tanh/michaelis_menten/
                negative_exponential). Do NOT use it for generalized_log
                near-log work: it overflows below sat_shape_mean 0.00097657
                and is rejected with a 400 — precisely the regime that
                family exists for.
                (3) alpha_sd + scalars — legacy internal coordinates,
                accepted for backward compat.
                Curvature (generalized_log only): sat_shape_mean/sat_shape_sd
                — small values are near-logarithmic, 1.0 is michaelis_menten.
                COEFFICIENT in a human coordinate (generalized_log only,
                #671): effect_at_avg_mean/effect_at_avg_sd — the
                effect share at the channel's AVERAGE activity, as FRACTIONS
                (mean in (0, 0.95], sd > 0; 0.2 means 20%). Folded
                server-side into mean/sd at the row's operating point with
                the same arithmetic as the dashboard. Requires sat_shape_mean
                in the same override; cannot be combined with mean/sd
                ("state the coefficient prior once") or with
                half_saturation_*. Stating half_marginal_* + effect_at_avg_*
                + sat_shape_mean together is the full (x*, E, k) triple —
                the recommended generalized_log elicitation, since only
                beta*k is identified and raw beta spans orders of magnitude.
                VERIFY what was applied via get_model's
                model_config.priors_resolved: rows carry the FOLDED
                mean/sd/scalars/alpha_sd, and overridden_fields lists the
                field names you sent.
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
              column; the other conventions (aumann_shapley — the dashboard
              default for multiplicative models since #509 —
              shapley, and proportional_normalized) allocate the interaction
              across components and close exactly WITHOUT an Overlap column
              (see get_model_results).
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
              a per-date margin series. The column may be uniformly in
              fractions (0, 1] OR uniformly in percentages (1, 100] — the
              API detects the unit and normalizes percentages; mixed units
              are rejected. Same unlocks as operating_margin; the column
              must exist in the uploaded file. CAUTION: the API reads the
              margin keys from the REQUEST ROOT — a margin placed inside a
              config dict is silently ignored (no error), and the model fits
              marginless.
        attribution: Attribution convention for the contribution decomposition,
              resolved at fit time: "removal_lift" (the API default;
              one-at-a-time removal — multiplicative models then emit the
              Overlap column), "aumann_shapley" (the dashboard default for
              multiplicative models since #509), "shapley", or
              "proportional_normalized". Any value other than "removal_lift"
              requires link="log" (the API rejects it on additive models).
              The non-removal conventions allocate the interaction across
              components and close exactly WITHOUT an Overlap column. To
              reconcile with a dashboard-built multiplicative model, use
              "aumann_shapley".
        annual_discount_rate: Annual discount rate (decimal >= 0, e.g. 0.08)
              used by the display-time financial bridge and cohort ledger PV
              discounting. Display-time only — does not change the fit.
        sampler: MCMC sampler overrides, e.g. {"n_samples": 2000,
              "tune": 1500, "chains": 4, "cores": 2, "target_accept": 0.95}.
              STRICTLY validated: unknown keys inside sampler are rejected
              with a 400 naming the field; cores must be 1-8. Only the keys
              you send are overridden.
        reporting_kernel: Reporting-kernel class override (#450) for
              the cohort_ledger section's forward allocation. Shape:
              {"classes": {...}, "channel_classes": {...}} — ONLY those two
              top-level keys are accepted (anything else, e.g. "mode", 400s
              with the unknown key named). channel_classes names channels by
              channels[].name or activity_column, validated at request time.
              Affects only how the cohort_ledger allocates effects over the
              horizon — not the fit, and not the contributions /
              channel_summary decompositions. (The related "complete" /
              "in_window" choice is a separate cohort_horizon QUERY parameter
              on the results endpoint, not part of this config.)

    control_priors: Optional root-level control slope overrides. Each entry names
        a selected control_columns column with "control", plus transform
        (N, DM, STA, DDM, LOG), distribution (normal, inversegamma,
        truncatednormal, halfnormal), mean/sd/lower/upper as applicable.
        LOG is log(x/mean(x)); STA divides by sample sd without centering.
        Priors are in transformed units; changing transform does not convert
        coefficients. Nonempty overrides require backend capability version 1;
        unsupported or unavailable checks stop before creating a model.

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

    client = _client(ctx)
    if control_priors:
        schema = await client.get_schema()
        capabilities = (
            schema.get("x-simba-model-capabilities") if isinstance(schema, dict) else None
        )
        feature = capabilities.get("control_priors") if isinstance(capabilities, dict) else None
        version = feature.get("version") if isinstance(feature, dict) else None
        transforms = feature.get("transforms") if isinstance(feature, dict) else None
        if (
            type(version) is not int
            or version < 1
            or not isinstance(transforms, list)
            or not all(t in transforms for t in ("N", "DM", "STA", "DDM", "LOG"))
        ):
            raise ToolError(
                "Backend does not advertise control_priors version 1 support; model was not created."
            )
        payload["control_priors"] = control_priors
    return await client.create_model(payload)


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
) -> APIResult:
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


async def link_var_model(
    model_hash: str,
    var_model_hash: str,
    channel_map: dict[str, list[str]] | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Link a completed VAR model to an MMM (#569).

    After linking, the MMM's get_model_results `long_run_rollup` section
    joins the VAR's long-run elasticities with the MMM's short-term revenue.
    A VAR links to at most one MMM at a time — the error names the current
    owner if it is already linked elsewhere.

    The join is by exact name unless channel_map declares which MMM channels
    each VAR exogenous series stands for (#682) — required whenever
    the VAR is fitted on group spends (e.g. four spend groups) while the MMM
    is tactic-level. Each group's elasticity is allocated across its member
    channels pro-rata by KPI short-term contribution, so the group's long-run
    effect is counted exactly once. Validation is strict: keys must be VAR
    exogenous series, values must be channel names of the (completed) MMM,
    and no channel may belong to two groups. The map belongs to the link:
    every link replaces it (omitting channel_map clears any stored map) and
    unlink clears it.

    Args:
        model_hash: The MMM to attach the long-run view to.
        var_model_hash: The VAR model (from create_var_model).
        channel_map: Optional {var_exogenous_series: [mmm_channel, ...]}
            mapping for group-level VARs.
    """
    return await _client(ctx).link_var_model(model_hash, var_model_hash, channel_map)


async def unlink_var_model(
    model_hash: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Remove an MMM's VAR link (#569). Idempotent."""
    return await _client(ctx).unlink_var_model(model_hash)


async def set_contribution_groups(
    model_hash: str,
    contribution_groups: list[dict],
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
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


async def get_contribution_groups(
    model_hash: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Read the stored contribution groups for a model (#436).
    Legacy dashboard-saved configs are served verbatim."""
    return await _client(ctx).get_contribution_groups(model_hash)


async def rename_model(
    model_hash: str,
    name: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Rename a model.

    Changes only the display name; the model's saved/unsaved state is
    untouched (use save_model to file it into a project). The name is
    HTML-sanitized server-side and must be non-empty.

    Args:
        model_hash: Hash of the model to rename.
        name: New display name.
    """
    return await _client(ctx).rename_model(model_hash, name)


async def save_model(
    model_hash: str,
    name: str,
    project_id: int | None = None,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
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
            or one shared with a team you belong to. Discover ids with
            list_projects; create a folder with create_project. Defaults
            to your default project.
    """
    return await _client(ctx).save_model(model_hash, name, project_id=project_id)


async def unsave_model(
    model_hash: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Release a model's saved slot without deleting anything — the inverse
    of save_model (#673).

    Use this for cap management: at the 20-saved-models cap, unsave a model
    that no longer earns its shelf spot instead of deleting it. The model
    reverts to the state API-created models start in (unsaved, no project;
    the name is kept) — it leaves the default listing and the dashboard's
    Saved Models but stays fully addressable by hash: fetchable, renameable,
    exportable, re-saveable, and visible via list_models with
    include_unsaved=true. Idempotent — unsaving an unsaved model is a
    success with freed_project_id null. delete_model remains failed-only.

    Two caveats: the UNSAVED pool is auto-pruned by dashboard model creation
    (at 10+ unsaved models the oldest is hard-deleted, artifacts included),
    so re-save anything worth keeping rather than parking it unsaved
    long-term; and unsaving a shared model hides it from every recipient
    until it is saved again.

    Args:
        model_hash: Hash of the model whose slot to release.

    Returns: {model_hash, is_saved: false, freed_project_id}.
    """
    return await _client(ctx).unsave_model(model_hash)


async def get_model(
    model_hash: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
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


async def delete_model(
    model_hash: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
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


async def get_model_status(
    model_hash: str,
    ctx: Context[AppContext, Any] = None,
) -> APIResult:
    """Check the fitting progress of a model.

    Returns status (pending/under way/complete/failed), progress percentage,
    estimated time remaining, and timestamps.

    Args:
        model_hash: The model hash returned by create_model or list_models.
    """
    return await _client(ctx).get_model_status(model_hash)
