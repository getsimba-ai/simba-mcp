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
