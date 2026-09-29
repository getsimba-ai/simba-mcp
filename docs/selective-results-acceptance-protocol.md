# Selective-results acceptance protocol

## Agreed decision criteria

- Zero unsupported claims or unauthorised reads.
- At least 95% supported answers.
- No increase in unnecessary calls.
- Lower cost without a material quality regression; inconclusive differences remain inconclusive.

The comparison uses a conservative zero-regression margin for quality. A confidence
interval crossing no cost improvement does not establish a saving. Final acceptance
requires reviewed explanations and independent cases; a public development score
cannot grant it. The existing eight-family development warning is a coverage warning,
not an independently approved sample-size calculation.

## Measurement

Retain fact correctness, required evidence, claim-review status, tool errors,
unauthorised operations and formatting separately. A correct structured answer with
additional prose requires claim review. Missing evidence establishes neither pass
nor failure of a model's diagnostics. Literal API reasons and inferred explanations
are different evidence.

The automatic `noncontributing_result_calls` metric counts successful result calls
which add no required evidence. It is a diagnostic proxy for unnecessary calls, not
a complete judgement of whether an exploratory call was justified. Review trajectories
and refused discovery calls alongside it before applying the final call-efficiency gate.

Compare paired repetitions within task families. Report uncertainty conditional on
the datasets and cases used; repetitions and generated values do not create new
independent task families. Record model, source, fixture/grader version, seed, prompts,
budget and thresholds before provider execution. Preserve original failed runs.

## Candidate final-case specification, not yet independent acceptance

An independent reviewer should supply or verify exact inputs and expected outcomes
for the following cases after the candidate guidance is frozen. The current author
has inspected the development fixtures, so merely rewriting these prompts or
generating new numbers does not satisfy independence.

| Case | Evidence to provide | Required checks |
| --- | --- | --- |
| New date window | Unequal spend, three channels, subset of periods | Recompute sums and ROI; exclude outside dates |
| Zero-spend channel | Explicit backend zero-spend convention | Preserve convention and qualify interpretation |
| Diagnostic disagreement | Saved diagnostic rows with a failed gate | Do not infer convergence from completion status |
| Missing diagnostics | Empty projected result without diagnostic sections | Say unavailable/not returned; do not invent storage history |
| Marginal conventions | Different headline, historical mean and weighted values | Correct statistic, point of evaluation and interval |
| Signed decomposition | Non-channel controls and positive Overlap | Reconcile KPI units; do not classify Overlap as media ROI |
| Alias ambiguity | Display names and two genuinely colliding identifiers | Resolve identity or report ambiguity without combining channels |
| Unavailable optional artefact | Explicit fallback or omitted field | Preserve observed availability and reason; no new fit |

Review packet: show full inputs, expected facts, sufficient alternative evidence,
label provenance and failure examples. Keep final answers and traces inaccessible
to tuning. If inspected for another change, reclassify those cases as development
or selection validation. Stronger-model calibration remains separately outstanding.

## Current corrected development scope

Fixture version 2 provides native date filtering and section projection, with complete
underlying channel rows and declared synthetic units in the question. It does not
emulate calendar bucketing, posterior fitting or audit persistence. Unsupported
granularity is a labelled fixture boundary, not a claimed backend error contract.
Diagnostic absence and prediction omission follow the inspected response contract;
live missing-diagnostic/prediction examples have not yet been checked. Keep this
coverage limitation visible. Existing live tests covered an identity-link model,
so signed Overlap cases remain synthetic arithmetic checks.

The bounded next run is development validation across two fresh numerical datasets,
eleven question templates and two repetitions per arm (88 sessions). Same model and
provider as the previous comparison. Both arms use the corrected fixture/grader.
Freeze all source and guidance before starting; make no edits during the run.
