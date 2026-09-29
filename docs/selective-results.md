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

Local regression: 451 tests passed, including independent result-selection and
paired-host mock tests. Lint, formatting, generated reference/Skill checks and
package build passed. The scripted evaluation completed two repetitions without
provider calls or real model fits. CI is tracked in the implementation PR. The
agent comparisons and remaining routing gap are described below. Issue #45 remains open; no
deployment or scientific-model validation is claimed.

## Bounded shorter-guidance iteration

The follow-up kept the result handler, shortened canonical guidance and made the
supplied-model path explicit. Both arms used the same semantic grader, with literal
field fidelity scored separately. Three repetitions used each original question;
two used frozen paraphrases. No prompt named the required result sections.
[Follow-up evidence](selective-results-followup-evidence.json) retains all 50
sessions, the post-hoc audit and eight prospective targeted sessions.

| Metric, full shorter-guidance comparison | Baseline | Shorter guidance |
| --- | ---: | ---: |
| Required evidence retrieved | 9/25 | 25/25 |
| No out-of-task/error calls | 9/25 | 23/25 |
| Frozen grader-v2 combined passes | 6/25 | 18/25 |
| Post-hoc grader-v3 corrected passes | 6/25 | 23/25 |
| Tool calls | 44 | 29 |
| Input tokens | 2,030,628 | 1,989,145 |
| Accounted cost | US$2.081273 | US$2.028165 |
| Median session duration | 5.34 s | 4.24 s |

Observed input-token reduction was about 2.0%, cost reduction about 2.6%. These are
small-sample observations, not general performance guarantees. Both arms had zero
unintended writes and zero bare-JSON passes. This experiment uses a different
rubric from the first comparison, so its pass rates must not be compared directly
with the first comparison's literal-field grades.

### Grading correction and prospective check

Five candidate diagnostic answers used `convergence: false` with an explicit
missing-saved-diagnostics reason. For the question asking whether saved evidence
establishes convergence, that is equivalent to unknown, not a claim the model
failed convergence. Grader v2 incorrectly rejected this representation. Grader v3
accepts the boolean only with a missing-evidence reason. Numeric zero, true,
failed-convergence claims, missing reasons and unsupported evidence still fail.

The original v2 scores are retained. The 23/25 figure is explicitly a post-hoc
regrade, not the frozen primary score. A new prospective paraphrase test then
passed both candidate diagnostic sessions. The grader evaluates bounded structured
facts and source evidence; it is not a general judge of every explanatory sentence.
Unrecognised nesting/wording can still fail, as shown by baseline old-artefact
answers that put the correct facts in an unsupported nested shape.

### Remaining routing gap and disposition

The two remaining full-comparison candidate failures both tried to request
`sections_available` as a section before recovering with `mroi_periods`. That name
is envelope metadata. A concise clarification was added to guidance, but both
prospective old-artefact candidate sessions repeated the invalid first request.
They recovered and returned the correct unavailable-evidence answer. Therefore the
clarification is documented, not claimed as a proven fix.

Retain the tested selection/disclosure implementation and the shorter guidance as
reviewable improvements. Retire the expanded guidance from the first comparison.
Do not add a summary tool on these results. **Keep #45 open and the PR in draft
until the legacy-artefact routing gap is fixed or explicitly accepted as a bounded
recovery limitation, and the change is reviewed and merged.** Do not spend further
on prompt tuning under this experiment.

Across all 108 sessions, cumulative accounted provider spend was **US$9.524580**
under the same US$10 cap, with no outstanding usage reservations. The first 50
sessions remain in their original evidence file; the second 50 plus eight targeted
sessions are in the follow-up file. Production backend behaviour, general host
coverage and scientific-model validity remain outside this evidence.
# Evaluation robustness expansion

The follow-up work applies the discipline described in
[Automating eval design and hillclimbing](https://claude.dev/blog/automating-eval-design-and-hillclimbing/)
to the existing runner. Earlier measurements and scores remain immutable.

- Grader version 5 has an explicit calibration corpus with correct, incorrect,
  contradictory and unsupported structured claims. These are engineering labels
  awaiting independent review. It rejects unknown additional fields instead of
  silently treating them as supported claims. Reason matching is deliberately
  bounded; an unfamiliar valid paraphrase requires review. Reports distinguish
  definite structured mismatches from pending review. Additional prose or fields
  prevent an overall quality verdict until reviewed, without making the requested
  numeric facts automatically wrong.
- JSON code fences are a formatting difference. Prose outside the parsed answer
  requires separate review; this is not a general natural-language claim judge.
- The expanded development suite contains eleven questions across six task
  families, including TV and combined ROI, unequal period ratios, non-windowed
  marginal ROI, decomposition values and explicitly authorised unavailable
  prediction evidence. All use one public synthetic dataset. They are not hidden
  acceptance cases and do not establish scientific model validity.
- The existing host command's `--results-robust` option freezes task definitions,
  arm guidance, catalogue, model, calibration and normalised source fingerprints
  before provider execution. Checkpoints reject drift. The runner retains its
  serial spend reservations and never automatically retries uncertain requests.
- Reports pair repetitions by task and arm, weight task families equally, and
  bootstrap families and paired repetitions within each task. Missing, duplicate
  or unfinished trials invalidate the comparison. Intervals are conditional on
  this dataset and family selection, not population-wide confidence claims.
- Proposed gates are zero structured/evidence/routing failures, no quality loss,
  at least eight task families and a five-percent cost saving supported by the
  interval. These thresholds need owner agreement. The current six-family suite
  cannot satisfy that proposed coverage gate.
- Final acceptance additionally requires independently reviewed labels, multiple
  datasets and previously unseen cases held by an independent owner. This command
  only runs development comparisons and cannot mark them accepted. A stronger-model
  sanity check also remains outstanding. No new prompt-tuning loop is introduced.

Ownership follows [the engineering objective](engineering.md): provider execution
stays in the existing adapter and CLI; `result_selection` owns task dispatch;
`result_grading` owns pure bounded grading; `result_calibration` owns labelled
grader fixtures; `evaluation.experiments` owns frozen-input validation and paired
assessment. Production tools do not import any of these evaluation modules.

## Robustness pilot stopped for grading review

The planned 66-session development comparison at source `84503db` was stopped
after 19 completed sessions and one interrupted session. Frozen grader 4 combined
correct structured facts with unreviewed explanatory prose in one pass flag. That
flag could not support a meaningful comparison. Its original scores are retained
in [the aborted pilot evidence](selective-results-robustness-evidence.json).

Grader 5 now records `pass`, `fail` and `review`. Unknown explanatory wording and
additional claims need review, while definite value/evidence/routing mismatches
remain failures. Quality differences and intervals are withheld while claims
remain unreviewed. This correction has local tests and a 20-example engineering
calibration corpus. It has not been prospectively validated in another paid run.
The corpus is included separately in the evidence file, not applied to overwrite
the frozen pilot scores.

Accounted cumulative spend is US$11.438494 against the authorised US$25 cap:
US$11.148900 known charges and US$0.289594 retained for unknown in-flight usage.
The remaining allowance is US$13.561506. The raw checkpoint retains its last
running status; the enclosing abort record is authoritative. No retry or new
provider run was started after the stop. The runner now also supports an operator
stop file at provider checkpoints, preserving reservations and partial evidence.

### Concrete review decisions before another comparison

| Example | Requested fact verdict | Remaining review |
| --- | --- | --- |
| Search revenue 500, spend 200, ROI 2.5, with a prose summary | Pass when the corresponding evidence was fetched | Check additional prose claims |
| Convergence false, with an unfamiliar explanation that diagnostics were not saved | Review, not a proved false answer | Confirm that the explanation expresses unknown convergence |
| Convergence true when diagnostics were not saved | Fail | Cannot establish convergence from missing evidence |
| Correct ROI plus an additional claim of causal validity | Requested numeric fields can pass | Extra claim remains unverified; overall acceptance is blocked |
| Correct final answer after requesting metadata as a result section | Facts can pass | Routing still fails; recovery is not a clean tool sequence |

Next: independently review the rubric and representative labelled answers, agree
quality and cost thresholds, then supply multiple datasets and externally held
acceptance cases. Only after those prerequisites should another frozen comparison
be used for acceptance. The issue and PR remain open and draft. The existing
historical-marginal routing gap is not waived or claimed fixed by this work.
