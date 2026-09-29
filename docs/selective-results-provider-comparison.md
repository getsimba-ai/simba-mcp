# Provider comparison for selective results

The MCP server and synthetic task contracts are provider-independent. The paid
evaluation host now separates the existing serial session and spend ledger from
Anthropic Messages and xAI Responses wire formats. It is not an arbitrary-provider
gateway: only explicitly configured models and modes are accepted.

Per [the engineering objective](engineering.md), `evaluation.hosts.models` owns
frozen request/pricing settings, `budget` owns conservative reservations and
settlement, and `session` owns the one serial request/dispatch loop. Provider
modules own schema conversion and response handling. The command reuses the same
cases, canonical MCP runner, authority checks, graders, checkpoints and reviews.
Historical Anthropic imports remain compatible; earlier model configuration and
evidence are unchanged. Production tools do not import the evaluation host.

Grok 4.7 is exposed through the global xAI Responses endpoint using XAI_API_KEY.
The key is supplied by the environment and never written into evidence. Only
local function tools are exposed; no hosted search or code execution is enabled.
Opaque reasoning is returned unchanged to subsequent requests but remains private.
No retry, provider fallback or replay occurs after a failed or uncertain call.
Deferred Anthropic tool search is not presented as an xAI capability.

The initial configuration is medium reasoning with 4,096 maximum output tokens.
This is an explicit experimental setting, not a claim that equal effort labels
mean identical compute across vendors. Official Grok 4.7 rates are US$2 input,
US$0.50 cached input and US$6 output per million tokens below 200,000 input tokens;
long-context rates are US$4, US$1 and US$12 respectively. Reservations use the
higher rates conservatively. Settlement uses the provider's per-request billed
cost in USD ticks, including its cache and reasoning charges, without counting
reasoning twice. Missing usage/billing retains the reservation and stops the run.
[Model](https://docs.x.ai/developers/models/grok-4.7),
[pricing](https://docs.x.ai/developers/pricing),
[cost accounting](https://docs.x.ai/developers/cost-tracking).

## Fast profile

The owner requested a faster option. `--model grok-4.7 --reasoning-effort low`
selects low reasoning on the same real model; the default remains medium. The
setting is frozen in each report and tested separately for quality, cost and
latency. This is not the separately branded Grok 4.7 Fast service, which the
official pricing page limits to Cursor and Grok Build rather than the public API.
There is no claim of speed improvement until measured. Output limits, read
authority, spend reservations and acceptance gates remain unchanged.

The owner authorised **US$500 cumulative**, with **US$67.781696** already accounted
for and zero reservations before integration. Each paid stage gets a smaller
explicit ceiling. The first comparison uses exposed validation cases and the
same frozen guidance on both models, measuring supported complete answers, every
explanatory claim, actual reads versus attempts, unnecessary calls, latency and
actual cost. The KPI prompt ambiguity is clarified prospectively; old results
stay unchanged. Adapter contract checks precede paid inference.

The first stage ceiling is **US$87.781696 cumulative**, at most US$20 additional.
Start with the three repaired failure families, two repetitions per model using
version 14 guidance. Review each completed group before proceeding; all six
answers per model must be complete and supported, without unsupported claims or
actual unauthorised reads/writes, before broadening to the other seven exposed
families. Alternate which provider goes first by family. These are single-arm
model diagnostics, not an estimate of the guidance change's causal effect.

Model selection is separate from final acceptance of the guidance change. A
selected model/configuration must be frozen before opening the new independent
packet, then compared with the original guidance on that same model. The existing
95% support, zero unsupported claims/unauthorised reads, call-efficiency and
cost/quality interval gates remain binding. Synthetic success does not establish
scientific MMM validity, production behaviour or owner merge approval.

## Partial observed results

The [preserved validation evidence](selective-results-provider-validation-evidence.json)
records source `754e3a1`, unchanged version 14 guidance and independently reviewed
synthetic answers. The requested fast profile is implemented and tested, but is
not yet accepted for PERF07.

| Profile | Completed answers | Supported | Mean session time | Completed-session cost |
| --- | ---: | ---: | ---: | ---: |
| Grok 4.7 low reasoning | 14 | 14 | 14.9 seconds | US$1.020270 |
| Sonnet medium reasoning | 16 | 14 | 6.7 seconds | US$3.267200 |

These incomplete groups have different case coverage. Times and costs are
descriptive, with unequal automatic caching, output lengths and provider order.
On the matched first KPI case, Grok low took 13.7/14.0 seconds and US$0.161530,
Grok medium 38.5/32.7 seconds and US$0.232630, and Sonnet 6.8/5.5 seconds and
US$0.409000. Two answers per profile cannot establish general superiority.

Sonnet's two window answers correctly calculate aggregate ROI, but assert that
the unweighted period mean would differ without reading period evidence. A
second independent interpretation confirmed this unsupported inference. The
initial charitable interpretation, its disclosed reconstruction and correction
are retained separately. Grok low read period rows before making that claim.
All completed reviews report zero unnecessary calls or unauthorised reads.

An xAI HTTP 429 stopped the remaining batch before its next answer. This is an
execution error, not an unsupported answer or a completed trial. The original
checkpoint and US$1.191824 reservation remain intact; no automatic retry occurred.
Accounted spend is US$73.493620 including that reservation and the older
US$0.289594 retained allowance. Subsequent continuation must carry both forward.
Private checkpoints now retain bounded provider error text and Retry-After for
diagnosis; public exporters exclude those bodies and all encrypted reasoning.
V4 remains unopened. Issue #45 remains open and PR #58 remains draft.

## Completed continuation and next validation

The separately frozen [continuation](selective-results-provider-continuation-evidence.json)
at `433bccb` completed the missing groups after a cooldown. Successful execution,
guidance and model settings were unchanged; only private HTTP error diagnostics
had changed. The original interrupted attempt and reservation remain preserved.

| Profile | Complete supported answers | Unsupported answers | Mean session time | Completed-session cost |
| --- | ---: | ---: | ---: | ---: |
| Grok 4.7 low | 19/20 | 1 | 14.0 seconds | US$1.516456 |
| Sonnet medium | 18/20 | 2 | 6.6 seconds | US$4.081000 |

Grok's remaining failure gives correct spend/revenue totals but appends a
revenue/spend quotient as their formula. Neither total uses that quotient.
The zero-unsupported-claims gate therefore fails for both profiles. The 95%
supported-answer threshold alone does not grant readiness. All completed reviews
report zero unnecessary calls and unauthorised reads. Timing and cost differences
remain descriptive, with caching and provider differences, not a guidance-effect
estimate or general model ranking.

Accounted cumulative spend is US$74.803606, including both retained allowances.
Version 15 prospectively clarifies separate sums versus ROI division and the fact
that different aggregation formulas can yield equal numbers. Its next bounded
validation compares V14 with V15 on three exposed families: aggregate windows,
channel comparison and restricted historical totals. This is not acceptance;
V4 remains unopened and no failure is rescored.
