# Independent selective-results acceptance, packet 2

## Decision: acceptance fails

The frozen comparison at `3f01e89` completed all 40 sessions. Independent review
supports **13/20 candidate answers (65%)**, versus **8/20 baseline answers (40%)**.
Seven candidate answers contain unsupported claims. They infer distribution tails
from summary statistics, favour a raw control-input direction without coefficient
evidence, misstate which sections were read, contradict explicit prior-field
semantics, or turn an unknown long-run effect into a claim that it is not zero.
All arithmetic, claims and calls are preserved in the [evidence record](selective-results-acceptance-v2-evidence.json).

Actual unauthorised reads and unintended writes are zero in both arms. Refused
unauthorised attempts and independently judged unnecessary calls are **6 candidate
versus 23 baseline**. Attempts are not reported as actual reads.

Family-weighted estimated cost saving is **22.75%**, with a conditional 95%
interval of **12.61% to 33.47%**. Lower cost is established on this packet. The
supported-answer difference is +25 percentage points, but its interval is
**-10 to +60 percentage points**, so quality nonregression remains inconclusive.
The zero-unsupported-claims and 95%-supported-answer gates also fail. Do not merge.

The run cost **US$11.177748**, taking cumulative accounted spend to **US$49.096088
of US$55**, including all earlier charges and the retained allowance. No provider
session or reservation remains from this run. All 546 local tests and all four
packet-head CI jobs pass; they do not establish answer quality.

These findings inform version 10 guidance, so this packet is now selection
validation material. Its original frozen acceptance result remains unchanged.
The next bounded check covers the five failing families with two repetitions per
arm, comparing version 10 with version 9 under the remaining cumulative cap.
Every candidate answer must be supported, with no actual unauthorised reads,
writes or increase in unnecessary calls. It will stop at a checkpoint if a
candidate readiness failure is found. A third independent packet remains private
until candidate readiness and freeze; no acceptance claim is carried forward.

## Protocol and preflight

Version 9 guidance and the existing Sonnet configuration were frozen before
release of this packet. A separate author prepared ten cases across ten declared
workflow families and two synthetic datasets, without seeing prior acceptance
answers, provider outputs or tuning guidance. The author did see the development
task schema, projection code and result-tool implementation. This is qualified
independence, not complete blindness. A different agent verifies all labels and
sufficient evidence paths before paid execution.

Preflight found packaging and representation defects: the dispatcher assumed a
single model identifier; new case identifiers used disallowed hyphens; diagnostic
and configuration fixtures needed alignment with recorded deployed table/nested
shapes. Evidence metadata also needed to require both compared channels and allow
the exact requested one-day evidence. These are prospective repairs with original
private specifications retained and expected answers unchanged. Guidance remains
frozen. Grader 13 preserves all earlier scores and derives the authorised model
identifier from each fixture. Wrong-model calls remain refused.

The final comparison uses the existing runner, provider adapter and enforced
ledger. Both arms use claude-sonnet-5-5, adaptive thinking, medium effort and a
4,096-token output limit, without temperature override or automatic retries.
Baseline guidance is the original pre-selective version; candidate guidance is
frozen version 9. Two repetitions per arm and case give 40 sessions, alternating
arm order. Every numerical answer, explanatory claim and call requires independent
hash-bound adjudication.

The agreed gates are unchanged: zero unsupported claims or actual unauthorised
reads, at least 95% supported answers, no increase in unnecessary calls, and lower
cost without quality regression. Conditional paired family-bootstrap intervals
must establish the cost and quality gates; uncertainty remains inconclusive.
Unauthorised attempts are reported separately from actual reads.

Prior accounted spend is US$37.918340 under the authorised US$55 cumulative cap,
including the retained US$0.289594 interrupted allowance. No real fits are allowed.
No tuning is permitted against this packet while retaining its acceptance label.

The cases test synthetic workflow and public saved-result contract correctness,
not scientific MMM validity or production reliability. Families are not crossed
with both datasets. Prior live coverage limits remain: signed Overlap, missing
diagnostics, control reference fields and audited prediction behaviour are not
newly verified by this comparison. Recorded deployed evidence confirms nested
config, diagnostic rows and sibling priors_resolved; the unobserved control
reference placement follows the public contract.

Acceptance and owner approval are both required before merging PR #58. Issue #45
stays open until accepted and merged.
