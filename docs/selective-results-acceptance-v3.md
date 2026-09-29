# Third independent selective-results acceptance protocol

Status: completed and independently reviewed. **Acceptance failed. Do not merge.**

## Reviewed result

All 40 sessions completed at `7263d3d`, with every answer and tool call independently
reviewed against the frozen packet and supplied contracts. The
[evidence record](selective-results-acceptance-v3-evidence.json) preserves original
mechanical scores, synthetic answers, trajectories and hash-bound reviews.

| Measure | Baseline | Candidate |
| --- | ---: | ---: |
| Supported answers | 11/20 | 16/20 |
| Answers containing unsupported claims | 8 | 2 |
| Incomplete answers with otherwise supported claims | 1 | 2 |
| Independently reviewed unnecessary calls | 2 | 0 |
| Unauthorised read attempts | 2 | 0 |
| Actual unauthorised reads | 0 | 0 |
| Provider cost, USD | 4.291498 | 4.190452 |

Both candidate KPI answers omit the requested combined Sales and Revenue totals,
despite correct per-date values. One historical mROI answer falsely says a date
filter selects returned rows, although the section is explicitly unwindowed.
One diagnostic answer says all-variable coverage cannot be established, contrary
to the supplied full r_hat contract. The reviewer distinguishes these explicit
contradictions from merely noting that payload metadata was not independently
checked. These four failures remain in the result.

Candidate support is 80%, below the required 95%. The zero-unsupported-claims
gate also fails. Estimated cost saving is **2.35%**, with a family-clustered 95%
interval of **-7.55% to 12.91%**. Quality difference is **+25 percentage points**,
with interval **-5 to +55 points**. Cost improvement and quality nonregression
are both inconclusive. The reviewed unnecessary-call gate passes; the section
completion proxy is retained separately and does not replace call adjudication.

Run cost US$8.481950 brings cumulative accounted spend to **US$66.961418 of US$70**,
including the retained older interrupted allowance. Reserved spend is zero and
no provider session remains. The remaining US$3.038582 cannot fund another
validation stage plus fresh acceptance comparison. No additional paid run has
started. All 607 local tests and all four CI jobs passed at the frozen source.

The original protocol follows. Any later tuning informed by these outcomes makes
these cases validation material, requiring new independent final acceptance cases.

## Subsequent validation decision

The owner subsequently authorised **US$90 total**, carrying all US$66.961418
forward. Version 14 uses these findings to test complete, concise requested
outputs and precise use of the existing window and diagnostic contracts. This
packet is now validation-only; its original failed acceptance result is unchanged.

The bounded validation reuses the three failure families (combined KPI totals,
historical mROI scope and diagnostic scope), with two repetitions per arm against
version 13, four sessions per family. The stage ceiling is US$70.961418 cumulative,
within the US$90 overall cap. Review each family before starting the next and stop
on a candidate readiness failure. Require all six candidate answers supported,
no unsupported claims or actual unauthorised reads/writes, and no increase in
independently reviewed unnecessary calls. Cost is observed, not acceptance proof.
The model configuration and grader remain unchanged. A separate author prepares
new private cases without this packet, outcomes or candidate guidance; release
requires readiness and another candidate freeze. No merge is authorised.

## Frozen protocol

Following targeted version 13 validation, the candidate guidance was frozen at
`40431fa` before the new packet was released. Its guidance fingerprint is
`23ecdc75faefc820b8d3002b29a1ea3c9465f9db62474cbb7ba53171f1708420`.
The original pre-selective guidance remains the baseline. Earlier failures and
mechanical scores remain unchanged.

The packet contains ten separately authored task families on two synthetic saved
datasets. The author avoided tuning transcripts, candidate guidance and previous
acceptance tasks, but incidentally saw a generator docstring and initial arithmetic
lines. This is qualified independence, not complete blindness. A separate verifier
knows earlier outcomes and first inspected this packet after the guidance freeze.
Numerical labels and every explanatory requirement receive independent checks.

Pre-run grader corrections recognise sufficient evidence across multiple reads,
including dated rows, single-date summaries and channel summaries with the same
window context. They reject incomplete coverage, mixed aggregate windows, spoofed
virtual evidence markers and disallowed sections. The prediction-boundary task
authorises only channel_summary. Attempts refused before execution are reported
separately from actual reads. These changes do not tune the frozen guidance or
change task questions, numerical labels or explanatory requirements.

The planned comparison is 40 sessions: ten families, two repetitions per arm,
alternating arm order, using the existing Sonnet provider adapter with adaptive
thinking, medium effort and 4,096 maximum output tokens. Source, task packet,
guidance, rubric, model configuration and calibration are frozen in the report.
All previous spend is included: US$58.479468 prior, US$70 cumulative cap and zero
current reservations. The existing request reservation mechanism must remain
enforced. An incomplete comparison cannot establish acceptance.

Every numerical answer, explanatory claim and tool call requires independent
adjudication bound to the exact answer and trajectory hashes. Acceptance requires
zero unsupported claims or actual unauthorised reads, at least 95% supported
answers, no increase in unnecessary calls, and lower cost without quality
regression. The predeclared family-clustered 95% intervals must support positive
cost savings and non-negative quality difference. Uncertainty is inconclusive.

Per [the engineering objective](engineering.md), the fixture module owns the new
synthetic data and labels. The existing results host owns evidence sufficiency
and authority enforcement; the canonical runner and provider adapter execute the
comparison. There is no second runner or backend implementation. Focused tests
cover legitimate alternative reads and misleading evidence, alongside existing
compatibility checks.

This evaluates synthetic workflow correctness, not scientific MMM validity,
population reliability or deployed audit behaviour. Issue #45 stays open and
PR #58 stays draft. Passing this protocol does not authorise a merge.
