# Native discovery: controlled host integration

Status: tested with synthetic backends, experimental. Keep the compact eager
catalogue as the operational fallback. Native discovery is not enabled by installing
this package or installing Skills, and it is not recommended as a new default.

## Ownership and mechanism

`evaluation/hosts/anthropic.py` owns the Messages API conversation and budget ledger.
`scenarios.py` owns synthetic prompts and scoring, reusing the canonical workflow
fixtures and `evaluation.runner.run_case` dispatch. `__main__.py` owns the command
and evidence files. This is an evaluation example, not a production agent service.
No provider SDK or new runtime dependency is added. Production server/tool modules
do not import this adapter. See the [engineering objective](engineering.md).

All 81 definitions still go to the provider. The adapter marks tools deferred,
leaving guidance eager, and adds native BM25 search. Provider-returned references
identify the discovered definitions; full search blocks remain in conversation
history. Only ordinary tool calls reach the existing MCP dispatch. The catalogue,
schemas, annotations and caller context are not mutated. The provider API accepts
input schemas, not MCP output schemas or annotations; those remain in the original
MCP registry and are identified by hashes in the evidence catalogue manifest. Annotations are not grants.

This follows the [official tool-search protocol](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool),
checked 29 September 2026. Provider references plus the hashed catalogue manifest identify
which definitions were selected; the provider's internal rendering is not observable.

## Run the synthetic comparison

Install the package from this branch. Supply `ANTHROPIC_API_KEY` through the process
environment, never in code, a command argument, or committed configuration. Then:

```shell
python -m simba_mcp.evaluation.hosts --mode both --samples 2 --cap-usd 1 --prior-usd 0 --output .codex/discovery/new-run.json
```

This is a paid command and may stop before completing under that example limit.
Choose an authorised cap. The fixed model is `claude-haiku-4-5-20251001`; native
search is `tool_search_tool_bm25_20251119`. Standard pricing used by the example is
US$1/million input and US$5/million output tokens; cache creation is conservatively
charged at twice input price. No caching is requested. Recheck provider pricing
before adapting the example to another model or rate.

The command runs analysis, profit optimisation, study review and a combined
results/study task. All backend actions use strict public fixtures and cannot reach
a live Simba backend. Guidance reads use packaged content. `--case cross_domain`
selects just the combined task. Fresh sessions are used between tasks/repetitions,
so earlier search references are not reused across context resets.

The default `--mode eager` is the tested full-catalogue fallback. Use `--mode deferred`
only for explicit native-discovery experiments. Provider failure stops the run,
retains the reservation and does not retry, silently switch modes or replay writes.
For a new run, use a new output file and carry the previous ledger's `prior + charged
+ reserved` into `--prior-usd` under the same cumulative cap. An existing output file
is never overwritten. Do not run multiple processes against one budget. If a real
integration has an uncertain write, reconcile it before any new session or fallback.

The example reserves a conservative request bound and persists it before each
provider call. Missing usage or interruption keeps that reservation. Evidence
contains synthetic prompts, arguments, responses, search results and usage, so this
logging policy must not be reused with private/live data without redesign.

## Support matrix

The same host also supports an experimental [role-view comparison](workflow-profile-evaluation.md)
through `--role-comparison marketer` or `--role-comparison reviewer` in eager mode.
The host now dispatches through the corresponding registered [server profile](tool-profiles.md);
invoking the comparison does not change a running production server.

| Surface | Native discovery | Eager fallback | MCP/Skills boundary |
| --- | --- | --- | --- |
| This Messages API host, fixed Haiku 4.5 model and BM25 tool above | API accepted, discovery observed, task limitations below | Tested on the same tasks | Actual local SDK dispatch with synthetic caller context; no native Skills installation |
| Claude desktop or Claude Code | Untested by this change | Existing catalogue remains available; this pilot does not certify those clients | MCP connection and Skill installation remain separate client setup |
| Other provider APIs/clients | Untested | No discovery support is assumed or silently emulated | No support claim from a provider name alone |
| Production remote MCP connector/authentication | Not tested here | Existing production server behaviour unchanged | This host example is not a remote connector deployment |

## Results, 29 September 2026

The [evidence record](native-discovery-evidence.json) contains the catalogue manifest,
exact prompts/fixtures, selected definitions, transcript blocks and per-turn usage.
Two repetitions per mode, alternating order, cover four tasks. These are development
measurements on a branch based on `b8b3701`, not an independent holdout study.

| Final task outcome | Compact eager | Native discovery |
| --- | ---: | ---: |
| Analysis | 2/2 | 2/2 |
| Profit optimiser | 2/2 | 1/2 |
| Study review | 2/2 | 2/2 |
| Combined results and study | 0/2 | 2/2 |
| Total passing sessions | 6/8 | 7/8 |
| Provider input tokens | 756,528 | 218,096 |
| Provider output tokens | 1,988 | 5,040 |
| Search operations | 0 | 21 |
| Ordinary tool calls | 14 | 16 |
| Calculated cost | US$0.766468 | US$0.243296 |
| Median session latency | 3.028 seconds | 7.825 seconds |
| Strict bare-JSON answers | 0/8 | 0/8 |

Native discovery used about 71% fewer input tokens and cost about 68% less, but
was slower and failed one optimiser trial: it sent bounds as an array instead of
the required lower/upper object. The mock refused the write. The agent then read
guidance and recovered, but the original invalid write attempt remains a failure.
In both eager combined-task trials, the agent confused the holdout's status with
the reason evidence was absent. Those answers remain failures. JSON in fences was
usable for fact grading, but no answer met strict bare-JSON formatting.

Do not interpret the aggregate success count as proof that discovery is superior.
It regressed on a write task in this cohort, and the sample is small. Keep this integration
experimental; retain eager mode and require broader acceptance before any
rollout decision. Scientific correctness and native-client behaviour remain outside
this test. Account/API availability does not imply task reliability.

### Targeted bounds correction

The compact optimiser description now states the required channel-to-lower/upper
object shape explicitly. Both modes received the same clarification. A separate
four-session rerun of the unchanged optimiser task passed 2/2 in each mode with
zero unexpected errors or unintended writes. Cost: US$0.174264. This addresses the
observed bounds failure without changing signatures, schemas or execution.
The earlier failure and comparison figures above are preserved; the correction
cohort is separate and does not turn earlier failures into passes or establish a
fresh full-suite performance estimate. The eager combined-task answer weakness remains.

The preliminary 12-session cohort is retained separately. It exposed ambiguous
synthetic identifiers and unsupported answer claims. Identifiers and required final
fields were clarified in both arms before the final cohort; its failures were not
relabelled. The final combined task was a separate four-session cohort.

This issue's experiments cost US$1.985387. Including previous experiments and the
existing US$1 interrupted-request reserve, cumulative accounting is US$7.410188
against the authorised US$10 cap. This is provider-usage accounting, not an invoice.

## Verification boundaries

Mocked tests cover zero-result search, reference history, pause continuation,
provider failure after a write without replay, fresh context, cross-domain dispatch,
schema preservation, budget exhaustion/unknown usage and separate format grading.
Provider trials verify actual search and repeated discovery from fresh sessions.
Mid-task compaction, real provider outages/zero-result recovery and production
authentication are not certified by mocks. No default setting or tool contract changes.
