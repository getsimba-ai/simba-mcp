# create_model: full contract

<!-- Generated from the handler docstring by simba_mcp.reference. -->

Create and start fitting a new Bayesian Marketing Mix Model.

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

calibration: Optional lift-test calibration: likelihood observations the
    fit must respect. Either {"tests": [{"test_id": ..., "version"?,
    "channel"?, "confirm_kpi"?}]} (recorded tests from
    list_incrementality_tests, each derived against THIS model's data),
    or {"units":
    "revenue" | "response", "observations": [{channel, x, delta_x,
    delta_y, sigma}]} for rows you derived yourself. If any test can't
    calibrate this model, nothing is created: the error has
    code "calibration_refused" and `tests` gives each test's reason.
    Preview a test's row with get_incrementality_test(model_hash=...).
    The derived rows calibrate this fit only; the model does not keep a
    link to the tests. To keep that lineage (the test then lists the
    model under used_by and can't be deleted), build through a study
    recipe or a recipe draft that references the tests.

Returns the model_hash for status polling.
