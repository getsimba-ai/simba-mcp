# Experiment screening priorities

All profiles expose `recommend_incrementality_tests`. Prerequisites: a saved model,
stored posterior marginal evidence and a backend supporting the test-priorities route.
Use model_hash directly. budget is an exposure scale, not a recommended test budget;
omit it only when the default sum of current spend is appropriate. hurdle is a
non-negative marginal-return alternative and limit is 1 to 50.

Retain method, basis, score_unit, currency, budget, spend_basis, period,
approximation_warnings, components, reason_codes and excluded channels. The score
is a local normal-approximation binary perfect-information value, not expected test
benefit, portfolio value, lift forecast or experiment design. Cross-channel dependence
is not modelled. Mean-active-period weights need not describe one shared calendar period.
An unavailable design_hint or test history remains unavailable; registry history alone
does not establish compatible geography/model coverage. Variance contraction or expansion
does not prove prior domination. Missing posterior evidence is excluded, not scored as zero.

On unsupported endpoint or permissions, retain the refusal and stop. Do not create a
test, fit, refresh or spend to repair screening. Human experimental design remains a
separate task. section=experiments-examples includes a supported and refused route.
