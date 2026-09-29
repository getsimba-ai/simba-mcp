# Third independent selective-results acceptance protocol

Status: pre-run verification. No acceptance result yet.

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
