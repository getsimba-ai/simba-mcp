# Grok selective-results acceptance

Status: preflight, no final comparison executed. Acceptance remains unmet.

Version 16 guidance passed a fixed, exposed validation on Grok 4.7 with low
reasoning and 4,096 maximum output tokens. Both arms supported all six answers.
The candidate made zero unnecessary calls versus one for the version 15 control.
There were no unsupported claims or unauthorised reads. This establishes readiness
for an independent comparison, not a causal quality gain or final acceptance.
The [hash-bound evidence](selective-results-v16-validation-evidence.json) preserves
all answers, calls and original automatic scores. Earlier failures remain intact.

Guidance and model settings were frozen before the separately authored version 4
packet was released for integration. Its author had inspected public contracts
and generic engineering instructions, but not candidate guidance or tuning
outputs when authoring it. Subsequent integration and independent review inspect
the adapter and other public fixtures. This is qualified independence, not a
claim that every participant is blind to earlier results.

## Frozen design

The planned comparison has ten task families across two synthetic datasets,
six paired repetitions per family, and 120 sessions. Both arms use the same Grok
configuration, fixtures, tools and questions. The control is the original
pre-selective guidance. The candidate is version 16. No further guidance tuning
uses this packet. All six repetitions use the authored questions because the
packet has no separate paraphrases. Repetitions do not create independent task
families.

Case order is shuffled within each repetition using seed 20260929 and recorded
in the frozen configuration. Arm order alternates baseline/candidate and
candidate/baseline across repetitions. All explanations and calls receive
independent review, including refused read attempts and actual reads separately.

Apply the unchanged gates: zero unsupported claims or unauthorised reads, at
least 95% supported candidate answers, no increase in unnecessary calls, lower
cost and no material quality regression. Use the existing family-weighted paired
hierarchical bootstrap with 4,000 resamples and seed 20260929. The 95% cost-saving
interval must have a positive lower bound; the quality-delta interval must have
a non-negative lower bound. Explicitly set minimum cost saving and the quality
noninferiority margin to zero. Uncertain findings remain inconclusive.

Complete the fixed schedule without success-based early stopping or adding
samples after inspecting results. An operational failure stops execution and
preserves the checkpoint, billed work and unresolved reservation. Any continuation
needs a separately recorded protocol. Partial execution cannot establish
acceptance. Preserve original grades separately from semantic adjudication.

The cumulative amount before this stage is US$79.396606, including US$2.672954
retained unknown allowances. The stage ceiling is US$100 within the owner's
US$500 total cap. No Sonnet tests or real model fits are authorised for this stage.

## Interpretation limits

Intervals condition on these ten families and two fixed datasets. They do not
estimate deployment-wide reliability. An all-success quality interval does not
prove absence of future failures. Automatic caching, output length and latency
are reported separately; equal model settings do not imply identical per-session
compute. This evaluates saved-result workflow correctness, not scientific MMM
validity. Issue #45 stays open and PR #58 stays draft until acceptance; merging
also requires explicit owner approval.

Integration follows [the engineering objective](engineering.md). The existing
fixture selector owns synthetic projection, the host command owns scheduling,
and the existing provider session, spend ledger and reviewed assessment remain
canonical. Packet preflight repairs and the final source/configuration hashes
must be recorded before provider execution.

## Prospective preflight repairs

Before any V4 provider session, integration aligned diagnostic identifiers and
table fields with the preserved contract, moved control references to the
appropriate configuration level, and applied the established zero-spend ROI
convention. Requested aggregate answers and authored arithmetic stayed unchanged.
The canonical fixture selector now supports native actual/model windows and
week, month and quarter totals for actual/model, coefficients and contributions.
Ratios are recomputed from sums and predictive intervals omitted. Default and
bundled reads remain valid. Monday-Sunday weeks are a declared synthetic
assumption because the public contract does not specify the weekly anchor.

The evidence checker now accepts a task's requested marginal channel without
requiring unrelated channels. Section-specific contribution windows preserve
full-period revenue evidence separately. Split channel-map reads accumulate.
Aggregate questions accept coefficient buckets; individual-period questions
still require evidence that preserves the requested periods.
Diagnostics accept either the complete R-hat table or the saved maximum and
parameter with a coefficient diagnostic. Safe default reads remain permitted;
forbidden prediction access remains a separate authority failure. Full datasets
and natural task prompts are preserved, with no answer schemas appended.

These changes are versioned prospectively as fixture 3 and grader 15. Original
scores are not recalculated. Local arithmetic and actual-dispatch checks verify
sufficient alternatives and reject wrong windows or missing channel evidence.
Monthly behaviour follows the public tool contract; this preflight does not
claim a new live backend verification.


