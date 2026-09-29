# Selective saved-result workflows

Related: [issue #45](https://github.com/getsimba-ai/simba-mcp/issues/45).

## Delivered behaviour

Use `get_model_results` with question-appropriate sections and date bounds.
Canonical results guidance now includes initial evidence bundles, interpretation
constraints and recovery examples. Native Skills are generated from that same
content. Full backend-default access and CSV behaviour remain unchanged.

Explicit JSON channel/grid requests add `_mcp_selection`, which reports requested
filters, changes by section, original/returned row counts, sampling and ambiguous
or unmatched channel aliases. Existing backend metadata and warnings are retained.
Alias matching remains permissive for compatibility; all matching exact names are
kept and collisions are disclosed. Contributions remain unfiltered.

Empty channel lists and grid limits below two retain their existing no-op behaviour
with disclosure. A collision with a backend `_mcp_selection` field returns an
actionable refusal rather than overwriting backend evidence. Unfiltered requests
remain available. Selection does not establish scientific validity or untouched
holdout status.

## Ownership

`tools/results.py` owns local selection and disclosure. The existing API client
owns query forwarding. Canonical guidance owns instructions and generated exports.
`evaluation/result_cases.py` owns public synthetic evidence, while the existing
runner executes tools and records measurements. The results host dispatcher adds
bounded query-aware alternatives to the existing provider adapter, without another
runner or a production dependency on evaluation. This follows the epic's
[engineering objective](https://github.com/getsimba-ai/simba-mcp/issues/38#engineering-objective-coherent-structure-and-shared-code).

## Scripted payload measurements

These measurements use one publishable synthetic model containing a 100-row
response curve and smaller analytical sections. Counts are representation-specific:
MCP content JSON and synthetic backend downloaded bytes are separate measurements.

| Question | Default MCP content bytes | Selected MCP content bytes | Default backend bytes | Selected backend bytes |
| --- | ---: | ---: | ---: | ---: |
| Historical ROI | 32,300 | 1,361 | 20,461 | 786 |
| Convergence evidence | 32,300 | 917 | 20,461 | 556 |
| Marginal ROI | 32,300 | 1,306 | 20,461 | 759 |
| Decomposition | 32,300 | 1,409 | 20,461 | 826 |

Each selected response retains the fixture evidence required for its question.
An additional historical-marginal task explicitly requests an unavailable old
artefact. Default results omit it, so that comparison is not equal-evidence and is
excluded from this table.

These are deterministic, synthetic payload comparisons, not observed provider
token savings or production network savings. Local channel/grid reductions happen
after download. Backend projection and download bounds remain separate work.

## Paired agent protocol

The comparison freezes current and revised results guidance. Each of five natural
questions runs five times per arm, with alternating arm order and fresh sessions.
Both arms receive the same compact full catalogue, provider model, temperature,
task prompts, fixtures and production handlers. Only guidance changes. On-demand
results guidance is frozen per arm as well.

The dispatcher supports valid alternative section combinations and call orders.
It rejects out-of-task discovery/mutations and unsolicited prediction-window
access. Source evidence and expected answer fields are graded separately. A correct
guessed answer cannot pass without the required returned evidence. Bare-JSON
formatting is recorded separately from extracted answers.

The expected-field gate is deliberately literal. A paraphrased reason or a display
name can fail it even when prose is broadly correct; such failures must not be
reported as evidence of numerical or scientific errors. The fixture supports one
declared native window and cannot validate arbitrary backend aggregation or audit
storage. Prompt paraphrase robustness and broader host coverage are not established.

Reproduce the paid protocol only with explicit provider authority and a budget:

```text
python -m simba_mcp.evaluation.hosts --results-baseline baseline-guidance.json --mode eager --samples 5 --cap-usd 10 --output comparison.json
```

The baseline file contains the three `get_workflow_guidance` response objects for
results `entrypoint`, `interpretation` and `tool-reference`, captured before the
change. The command refuses to overwrite evidence and retains reservations for
requests with unknown usage. Use `--prior-usd` when continuing a stopped budget.

### First comparison: expanded guidance, 29 September 2026

The frozen comparison completed all 50 sessions for US$4.737691 under its US$10
cap, with no outstanding usage reservations. Model: `claude-haiku-4-5-20251001`,
temperature zero. [Publishable evidence](selective-results-evidence.json) retains
every trial, including failures, usage, source hashes and frozen guidance.

| Metric | Current guidance | Revised guidance |
| --- | ---: | ---: |
| Sessions | 25 | 25 |
| Required source evidence retrieved | 10/25 | 24/25 |
| Expected answer fields matched | 15/25 | 5/25 |
| No out-of-task/error calls | 11/25 | 1/25 |
| Combined strict pass | 4/25 | 0/25 |
| Tool calls | 43 | 51 |
| Provider input tokens | 1,994,066 | 2,639,385 |
| Provider output tokens | 9,659 | 11,189 |
| Accounted provider cost | US$2.042361 | US$2.695330 |
| Median session duration | 4.69 s | 5.96 s |

Both arms had zero unintended writes and zero bare-JSON passes. Extracted fenced
JSON was graded independently. Display-name substitution, changed output field
names and paraphrased reasons contribute to expected-field failures; these are
not all numerical or scientific errors. Unnecessary `list_models`/`get_model`
calls are genuine routing overhead under the known-model task contract, even
though those reads are harmless. They were refused by the fixture dispatcher.

**First-candidate acceptance failed.** The expanded guidance retrieved more of the required
evidence but increased input tokens and accounted cost by about 32%. It does not
demonstrate overall task improvement, lower cost or lower latency. Keep that first candidate retired; do not close #45 on this evidence.

Next work: diagnose why the expanded guidance induces extra discovery; simplify
the known-model path; refine task output requirements and semantic grading before
freezing the next experiment. Preserve these original scores and report any
post-hoc analysis separately. Then rerun a bounded comparison, including held-back
paraphrases, under explicit trial authority. Do not reclassify failed trials as
passes or claim the current test established scientific correctness.

## Summary-tool decision

Defer `get_model_summary` in this implementation. Existing selectors can return the
required synthetic evidence with much smaller payloads, and there is no comparative
evidence that an additional tool improves routing. Revisit only with a specific
residual routing failure that survives better guidance and a controlled comparison.
This is a scoped engineering deferral, not proof that another tool could never help.

## Verification and remaining acceptance

Local regression: 449 tests passed, including independent result-selection and
paired-host mock tests. Lint, formatting, generated reference/Skill checks and
package build passed. The scripted evaluation completed two repetitions without
provider calls or real model fits. CI is tracked in the implementation PR. The
separate live agent acceptance failed as shown above. Issue #45 remains open; no
deployment or scientific-model validation is claimed.

## Bounded shorter-guidance iteration

The follow-up retains the tested result handler, shortens canonical guidance and makes the supplied-model path explicit. Both arms use the same revised semantic grader, with literal output fidelity reported separately. The original first-comparison record is immutable. Three repetitions use the original question and two use frozen paraphrases; neither question names the required sections. Provider comparison is in progress and remains inside the original cumulative US$10 cap. No acceptance claim is made before completion.
