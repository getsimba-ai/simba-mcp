# Corrected-contract development comparison

## Decision

The frozen fixture-2, grader-8 comparison completed all 88 sessions on Claude
Haiku 4.5. It does **not** meet final acceptance. Original scores and synthetic
answers are retained in [the evidence record](selective-results-contract-evidence.json).
The [agreed protocol](selective-results-acceptance-protocol.md) remains binding.

Two generated datasets, eleven question templates and two repetitions per arm
exercise six task families. These are development cases, not independent holdouts.
Both arms used the same corrected contracts. Source and guidance stayed frozen
throughout execution; implementation commit `3e56c8f` contains the tested source.

| Observation | Baseline | Candidate |
| --- | ---: | ---: |
| Sessions | 44 | 44 |
| Required evidence retrieved | 32 | 44 |
| Frozen fact passes | 24 | 32 |
| Frozen fact failures | 16 | 8 |
| Frozen fact verdicts needing review | 4 | 4 |
| Answers with additional claims needing review | 44 | 44 |
| Tool errors | 53 | 1 |
| Successful result calls adding no required evidence | 13 | 7 |
| Provider cost, USD | 5.525427 | 3.627635 |

Fact verdicts are not supported-answer rates. All answers contain prose requiring
review, and fact grading includes the requested output format and rounding.
Tool errors largely reflect refused discovery calls in the synthetic dispatcher,
not live API failures. The result-call measure is a proxy, not a complete audit of
unnecessary calls. Neither measure proves the zero-unauthorised-read gate.

The family-weighted cost-saving estimate is 24.46%, with a 95% bootstrap interval
from -1.56% to 41.05%. The interval includes a cost increase, so lower cost is
**inconclusive**. Weighting is equal across task families, not proportional to
session count. The interval conditions on these synthetic datasets and families.

## Failures retained

Candidate aggregate-ROI failures include both failure to round as requested and
incorrect arithmetic. Missing optional artefact answers sometimes infer storage
history, or absence of all model outputs, from a projected empty response. Those
explanations are unsupported by the returned evidence. Nested answer shapes and
reason paraphrases also affect strict grades; preserve original scores and label
any subsequent semantic adjudication separately.

The preceding grader-7 contract comparison was stopped after eight completed
sessions (nine trial records including the interrupted trial). It incorrectly
required a separate channel map despite sufficient inline channel identity.
Grader 8 fixes that requirement prospectively. The aborted run cost USD 0.905828
and establishes no comparative effectiveness result.

## Budget and verification

The completed run cost USD 9.153062. Cumulative accounted spend is USD 21.497384
of USD 25, including the retained USD 0.289594 allowance for older interrupted
usage. USD 3.502616 remains; no new provider run is currently scheduled.

On implementation commit `3e56c8f`, 484 local tests and all four CI jobs passed.
Lint, formatting, generated exports, package build and isolated wheel smoke passed.
These verify implementation, not scientific validity or independent acceptance.

## Remaining gates

- Finalise and review independently authored acceptance fixtures and their labels.
- Review all explanations before claiming a supported-answer rate.
- Resolve or explicitly disposition numerical, interpretation and routing failures.
- Demonstrate the agreed quality, access, call-efficiency and cost thresholds.
- Obtain approving PR review and merge before closing issue #45.

The PR remains draft. Shared ownership follows [the engineering objective](engineering.md):
fixtures, dispatch, grading and assessment retain separate owners and reuse the
existing runner and provider adapter. No production service or second runner is added.

## Independent agent review and prospective correction

A separate agent reviewed the rubric without the tuning transcripts, comparison
reports, previous answer reviews or fixture source. It did inspect development
task definitions and calibration examples, so this is not a fully blind review
or human approval. Ten fresh case specifications were authored and retained
separately from tuning. They are unexecuted and still need fixture and label
finalisation; their existence does not establish held-out acceptance.

The review exposed a diagnostic grading defect outside the current absence-only
development questions: an absence answer could pass a task expecting a genuine
failed diagnostic. Grader 9 restricts absence equivalences to the exact absence
contract and checks other diagnostic tasks against their declared expected fields.
A regression covers failed gates, passing gates and additional required fields.
The original grader-8 comparison above is unchanged and has not been rescored.
The prospective correction passes all 485 local tests, including the independent
reviewer's diagnostic probe; source/test formatting and lint also pass.

Remaining harness readiness work is concrete: subset-window tasks need task-specific
evidence validation, unauthorised read attempts and actual reads need distinct
reporting, and the unnecessary-call proxy needs trajectory adjudication. The current
bounded development rubric must not be presented as a general acceptance grader.
