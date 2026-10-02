# What to test next

`recommend_incrementality_tests(model_hash, budget=None, hurdle=1.0, limit=5)`
reads a saved model's marginal-return summaries and ranks channels for further
experiment investigation. It never fits a model, changes spend or starts a test.
It requires a backend with `/api/v1/models/{hash}/test-priorities` support.

Example with a synthetic model you can access:

```json
{"model_hash":"YOUR_SYNTHETIC_MODEL_HASH","budget":10000,"hurdle":1.0,"limit":5}
```

The tool needs `read:results`. Optional recorded-test history also needs
`read:models`. A results-only key receives `history_unavailable` rather than
information about tests outside its scope.

## Meaning of the score

The server computes an approximate, local binary expected value of perfect
information. It compares two hypothetical marginal actions: expose an amount
of spend to a channel's marginal return, or retain its hurdle-valued alternative.
The score is expected best utility with perfect information minus the best
expected utility with current information. It uses the stored posterior **mean**,
not the median, and approximates a normal standard deviation from the width of
the stored 94% highest-density interval.

For mean `mu`, standard deviation `sigma`, hurdle `h` and exposure `S`:

```text
a = abs(mu - h) / sigma
score = S * (sigma * normal_density(a) - abs(mu - h) * normal_tail(a))
```

Zero uncertainty or zero exposure gives zero information value. Current funding
status does not determine the score. This follows the optimal-current-action
definition of information value, rather than regret from retaining a known bad
action. See [Heath, Manolopoulou and Baio, section 2](https://discovery.ucl.ac.uk/id/eprint/1467157/2/Heath_Estimating%20the%20expected%20value%20of%20partial%20perfect%20information%20in%20health%20economic%20evaluations.pdf).

`budget` is an exposure scale, **not a recommended experiment budget**. The
server distributes that scale in proportion to recorded current spend. Those
values use each channel's mean active period and need not represent one common
calendar period. Without an explicit budget, their sum is used. Zero-spend
channels receive zero exposure. No hypothetical allocation is invented.

Scores use the model's revenue units. `currency` can be absent, in which case
clients must not invent a currency symbol. This local linear approximation is
not a prediction of changing an entire channel budget. Channels are assessed
separately, ignoring joint uncertainty and portfolio constraints. A real test
provides less than perfect information, incurs costs, and can be infeasible.
Scores are not expected test benefit, detectable lift or a mandate to test.

## Inspectable evidence and limitations

Each row includes the mean, available median, approximate standard deviation,
stake, spend share, hurdle-crossing probability, original interval and reason
codes. The response always discloses the normal and HDI-width approximations.
An asymmetric posterior is not made normal by this approximation. Missing
posterior means or intervals are excluded explicitly, not replaced with zero.

Native scalar coefficient contraction is `1 - posterior variance / prior variance`
when an exact parameter match and supported prior distribution exist. Half-normal
and truncated-normal scales are converted to actual variance. Unsupported priors,
time-varying coefficients and unmatched names yield `prior_unavailable`. Contraction
and completed-test recency only break ties, never multiply the score.

Results describe one model. A recorded hierarchy identity can be a brand rather
than a geographical market, so the tool does not infer geographical coverage or
pool independent market fits. Registry history is unknown when its scope cannot
be matched. `design_hint.available` is false because valid experiment design
requires additional inputs; no minimum detectable effect is invented.

## Architecture

Following [the engineering objective](engineering.md), the incrementality tool
owns only HTTP transport and public descriptions. The application owns the
scientific method, permissions and stored-artifact reads. MCP returns server
fields without recalculation. Existing registry tools and result contracts remain
unchanged. No new runtime dependency is required.
