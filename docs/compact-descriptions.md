# Compact tool descriptions

An opt-in mode shortens the three largest descriptions: `create_model`,
`get_model_results` and `run_optimizer`. The other 78 descriptions remain intact.
Full handlers, names, signatures, input/output schemas, effects and error handling
retain their existing owners. `catalogue.py` owns wording and guidance mappings only.
This follows the [engineering objective](engineering.md).

## Enable and roll back

Set `SIMBA_TOOL_DESCRIPTIONS=compact` in the server process environment before
starting it, for either stdio or HTTP. In PowerShell:

```powershell
$env:SIMBA_TOOL_DESCRIPTIONS = 'compact'
simba-mcp
```

For a managed MCP client, set the same value in that server's environment configuration
and restart its process. Reconnect clients so cached tool definitions are refreshed.
HTTP clients sharing a process see the same startup mode; this is not a per-caller setting.

To roll back, set the variable to `legacy` (or remove it) and restart/reconnect.
There is no persisted-state migration. Invalid values fail startup. Legacy remains
the default; these pilot results do not authorise a default change.

The [compact reference](tools-compact.md) links to the preserved [full reference](tools.md).
Full contracts are also packaged as `tool-reference` guidance sections for topics
`mmm`, `results` and `optimiser`. No extra backend request is required to read them.
Descriptions retain common nested field names, important units, side effects,
recovery actions and advanced guidance pointers.

## Reproduce the offline comparison

```shell
python -m simba_mcp.reference --check
python -m simba_mcp.guidance --check
python -m simba_mcp.performance --description-mode legacy --encoding o200k_base --output-dir .codex/comparison/legacy
python -m simba_mcp.performance --description-mode compact --encoding o200k_base --output-dir .codex/comparison/compact
python -m simba_mcp.evaluation --description-mode legacy --samples 3 --output-dir .codex/comparison/legacy
python -m simba_mcp.evaluation --description-mode compact --samples 3 --output-dir .codex/comparison/compact
```

These commands make no provider calls or real fits. Surface reports include every
tool's position, description, input schema and output schema measurements. CI retains
both modes. Tests check structural equality and original wrapped-handler identity
for all 81 tools, with success/refusal/invalid-input behaviour exercised by the
existing domain tests and 14 synthetic workflow cases. This is not a live backend
test for every handler.

## Observed comparison, 29 September 2026

Measured on the working tree based on `fbddcb7`, Python 3.11.9, MCP SDK 2.2.0,
HTTPX 0.28.1, Pydantic 2.13.5 and tiktoken 0.14.0. The curated
[evidence record](compact-description-evidence.json) retains source/surface digests,
per-tool measurements, pilot settings, prompts and session measurements.

| Measure | Legacy | Compact |
| --- | ---: | ---: |
| Tools-list result JSON, UTF-8 bytes | 165,724 | 140,517 |
| Same JSON, estimated o200k_base tokens | 37,199 | 31,693 |
| Description field JSON bytes, summed | 91,413 | 66,206 |
| Input-schema field JSON bytes, summed | 50,646 | 50,646 |
| Output-schema field JSON bytes, summed | 6,787 | 6,787 |
| Scripted contract trials passed | 42/42 | 42/42 |
| Agent sessions passed | 12/12 | 12/12 |
| Agent input tokens, provider-reported | 1,151,363 | 974,165 |
| Agent output tokens, provider-reported | 3,250 | 3,280 |
| Tool calls | 15 | 15 |
| Repair calls / unintended writes | 0 / 0 | 0 / 0 |
| Provider cost at published standard rates | US$1.167613 | US$0.990565 |
| Session latency median, seconds | 3.132 | 3.125 |

The catalogue JSON shrank 15.2%, estimated tokens 14.8%. Agent input usage fell
15.4% and calculated provider cost fell 15.2% in this pilot. Latency medians were
essentially unchanged; no latency improvement is established. MCP output schemas
were preserved, including their 6,787 bytes. This change does not address output
schema or text/structured-result duplication.

### Agent protocol and limitations

The pilot used the Anthropic Messages API with `claude-haiku-4-5-20251001`,
temperature 0, maximum 1,200 output tokens per turn and six turns per session.
No prompt caching was requested. Both modes provided all 81 tool names, descriptions
and input schemas in the same order. This direct API adapter does not send MCP
output schemas/annotations and does not test native-client discovery or Skills.

Four tasks each ran three repetitions per mode, alternating mode order by repetition:
read a completed model's selected results, submit a model with explicit sampler
settings, preserve a coefficient prior override, and queue constrained profit
optimisation. The prompts stated that schema/capability preflights were already
complete. Actual tool dispatch used the shared evaluator's strict synthetic HTTP
exchanges. Model calls were paid; backend calls were mocked and no fits ran.

Success required the expected backend sequence and settings, saved-answer facts,
and zero unintended writes. A singleton result list or `channel_summary` wrapper
was normalised before comparing the final answer. Provider usage includes all
turns, tool definitions and any repair/guidance turns. No guidance calls were needed
in the final cohort, so advanced guidance retrieval effectiveness remains untested.

A preliminary diagnostic attempt exposed missing sampler/prior field names in the
first compact wording. Those were restored before freezing the final comparison.
It also exposed overly strict answer-format scoring and an ambiguous results task;
the final protocol specifies the selected section and accepts equivalent wrappers.
Preliminary failures are retained separately and excluded from the final cohort,
not relabelled as passing. Two old synthetic fixture errors (prior field names and
an infeasible single-channel upper bound) were corrected in both arms before testing.

Final cohort cost was US$2.158178. Recorded preliminary usage cost US$0.822049;
an interrupted request has unknown usage, conservatively reserved at US$1. Total
accounted usage plus that reserve is US$3.980227, below the authorised US$10 cap.
Costs use [Anthropic's standard pricing](https://platform.claude.com/docs/en/about-claude/pricing),
checked 29 September 2026: US$1 per million input and US$5 per million output tokens.
This is usage-based accounting, not a reconciled invoice.

The pilot is small, uses one model and synthetic tasks, and informed the wording
during development. It is not an independent holdout study or proof of scientific
accuracy, universal quality equivalence, eager/deferred client gains or production
performance. Wider client coverage, advanced guidance tasks and approved numerical
quality/performance budgets remain open under issues #40 and #42.
