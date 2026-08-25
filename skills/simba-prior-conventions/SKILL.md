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
