# Selective-results guidance validation

Guidance version 7 consolidated the entry point and interpretation reference to
remove duplication, preserve the full API reference and require evidence for
actions described in answers. Its eight-session paired Sonnet validation failed:
three of four candidate answers were supported, versus all four controls. One
candidate answer incorrectly described 94% HDI endpoints as 3% and 97% quantiles.
The numerical bounds were correct, but this additional assertion was unsupported.

Both arms made two unnecessary calls by guessing a year absent from the question.
No actual unauthorised reads or writes occurred. Every answer and call has an
independent hash-bound review in the [evidence record](selective-results-v7-validation-evidence.json).
These reused cases are selection validation, never final acceptance.

The completed run cost US$2.029462, taking cumulative accounted spend to
US$35.094472. The owner has authorised a US$55 cumulative cap, including all
historical charges and the US$0.289594 retained interrupted allowance.

Version 8 adds a general distinction between HDI endpoints and equal-tailed
quantiles, including when field names contain percentile numbers. A new bounded
validation compares version 8 with version 7 using the same two cases, two
repetitions and alternating arm order. Its stage cap is US$38.094472 cumulative.
Readiness requires all four candidate answers supported, no actual unauthorised
reads or writes, and no increase in unnecessary calls. The new ten-case
independent acceptance packet remains unopened until this gate passes.

The previous interrupted acceptance packet has been retired to validation because
it informed subsequent guidance changes. Its original scores and failures remain
unchanged. This work assesses synthetic workflow correctness, not scientific MMM
validity. Acceptance and owner approval are both required before merging PR #58;
issue #45 remains open.

## Version 8 result and next validation

Version 8 also failed: candidate 3/4 supported versus control 4/4. The HDI
interpretation was correct, but one answer incorrectly forbade all averaging of
period mROI, despite the declared historical averaging conventions. Both arms
again made two unnecessary date guesses, with no actual unauthorised reads or
writes. [The complete evidence](selective-results-v8-validation-evidence.json)
preserves all eight answers and independent reviews. Cost US$2.017756 takes the
cumulative ledger to US$37.112228 of US$55, with no reservation.

Version 9 explicitly separates aggregate ROI from historical mROI averaging.
The next validation targets this marginal case with two repetitions per arm,
under a US$38.612228 cumulative stage cap. Both candidate answers must be fully
supported, with no unauthorised reads/writes or increase in unnecessary calls.
The independent acceptance packet remains unopened.
