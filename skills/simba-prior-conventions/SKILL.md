---
name: simba-prior-conventions
description: Simba prior-override payload conventions for create_model — smart-default merging, strict field rejection, the half-saturation/half-marginal/half-life anchor families and which combinations are invalid. Use before constructing any priors[] override through the Simba MCP tools.
---

# Simba prior payload conventions

## The merge model

Priors are smart defaults (cost shares, industry benchmarks via
`total_media_effect`, channel-type detection) with per-channel overrides
merged ON TOP. Each `priors[]` entry names a `channel` (matching
`channels[].name`) plus ONLY the fields to override — everything else keeps
its smart default.

## Strict rejection (#630)

Unknown keys in a `priors[]` entry are rejected with a 400 naming the field
— they used to be dropped silently, fitting a hybrid model. Common misses:
`beta`/`beta_mean` → `mean`, `beta_sd` → `sd`, `sat_shape` →
`sat_shape_mean`. `name` and `parameter` are rejected too. The same
strictness applies to `config.sampler` and `config.var_priors` — but NOT to
the request root or `config` itself, where unknown/misplaced keys are
silently ignored (so placement mistakes fit a wrong model without error).

## Anchor families — pick ONE per concern

Carryover (adstock):
- Preferred: `half_life_lower`/`half_life_upper` (periods until effect
  halves) over the legacy `decay_lower`/`decay_upper`.
- `theta_mean`/`theta_sd` only with `adstock_type="delayed"`;
  `dual_weight_mean`/`dual_weight_sd` only with "dual_geometric".
- Adstock types are geometric, delayed, dual_geometric — there is no
  power-law adstock.

Saturation:
- Preferred: `half_saturation_mean`/`half_saturation_sd` — the
  50%-of-maximum-response point in the channel's ACTIVITY units. Cannot be
  combined with the legacy `alpha_sd`/`scalars` pair in the same override.
- `sat_shape_mean`/`sat_shape_sd` only with
  `saturation_type="generalized_log"` (small = near-logarithmic, 1.0 ≈
  michaelis_menten).
- `half_marginal_mean`/`half_marginal_sd` (generalized_log ONLY): the
  activity level where MARGINAL returns have halved. Use it instead of
  half_saturation at near-logarithmic curvature — the 50% point overflows
  below sat_shape ≈ 0.00098 and 400s, while the half-marginal point is
  finite at every shape. Cannot be combined with the other two anchors.

## Reading posteriors back

`get_model_results` sections `posterior_transforms` (the importable
transform-parameter grid, keyed by activity column — join via
`channel_map`) and `posterior` (94% HDIs) close the prior → posterior loop
for the next fit.


### Explicit control priors and transforms

Use `control_columns` to include controls and optional `control_priors` to
configure them. Overrides select an exact column via `control`; media `priors`
continue to select a channel via `channel`.

```json
{"control_columns": ["price", "discount_depth"], "control_priors": [
  {"control": "price", "transform": "LOG", "distribution": "normal", "mean": -1, "sd": 0.5},
  {"control": "discount_depth", "transform": "N", "distribution": "normal", "mean": 1, "sd": 0.5}
]}
```

These are illustrative coefficients, not fitted estimates or recommended priors.
Native transforms: N = x; DM = x/mean(x); STA = x/sample_sd(x) without centering;
DDM = x/mean(KPI); LOG = log(x/mean(x)), requiring positive x.
Under a log link, a LOG coefficient is an elasticity; N is a semi-elasticity.
Changing a transform does not convert prior units: explicitly choose suitable
coefficient priors. Normal and inversegamma use mean/sd (positive mean for
inversegamma); truncatednormal also requires ordered lower/upper bounds;
halfnormal uses only sd. Unused fields, unknown keys, null field values and
nonselected/duplicate controls are rejected. Omitted fields preserve applicable
smart defaults; changing family clears inapplicable bounds/mean.

Nonempty overrides preflight `get_data_schema` for
`x-simba-model-capabilities.control_priors` version 1 and all five transforms.
Unsupported, malformed or unavailable capability checks stop before creation;
never retry by removing requested settings. Omitted/None/empty overrides keep
legacy calls unchanged. Backend support must be deployed before using this
option. Direct REST clients must perform the same capability check and put
`control_priors` at the request root. Check `get_model`'s resolved priors and
`overridden_fields` after creation. Prediction uses existing fit-time constants;
this feature does not change preprocessing split order or fit a model for you.
