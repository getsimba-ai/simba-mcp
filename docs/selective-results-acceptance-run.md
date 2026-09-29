# Selective-results acceptance comparison

## Decision: do not merge

The frozen 40-session comparison on implementation commit `77732d4` completed.
Separate agent adjudication covered all 40 answers and every trajectory, preserving
original automatic grades in the [evidence packet](selective-results-acceptance-evidence.json).
Acceptance fails: candidate supported answers are 14/20 (70%), below 95%, and six
answers contain unsupported explanatory claims. PR #58 remains draft and issue #45
stays open until acceptance and an approved merge.

| Reviewed measure | Baseline | Candidate |
| --- | ---: | ---: |
| Supported answers | 8/20 | 14/20 |
| Answers with unsupported claims | 12 | 6 |
| Required evidence retrieved | 16/20 | 20/20 |
| Unnecessary calls | 23 | 0 |
| Refused unauthorised read attempts | 15 | 0 |
| Executed unauthorised reads | 0 | 0 |
| Provider cost, USD | 2.354144 | 1.520950 |

Estimated family-weighted saving is 35.39%, with a 95% interval of 16.71% to 49.74%.
Reviewed supported-answer improvement is 30 percentage points, interval 0 to 60.
The cost and conservative zero-regression gates pass on this synthetic packet;
the absolute quality and zero-unsupported-claim gates fail. These intervals are
conditional on these ten case families and synthetic inputs, not population or
scientific generalisation. Repetitions are paired, not new independent cases.

The six candidate failures are cases D, F and H in both repetitions:

- D: projected missing diagnostics were treated as proof that nothing was saved.
- F: correct 130-unit reconciliation accompanied unsupported media-synergy and raw
  Weather-direction claims.
- H: the optional artefact fallback was expanded into unsupported exclusions of
  data/configuration causes and unverified availability of other artefacts;
  ordinary ROI was suggested as an alternative to historical marginal ROI.

Full-response semantic adjudication accepts supported paraphrases and explains
borderline wording explicitly. For example, E's null historical_average field is
an output-format mismatch but its explanation explicitly states neither historical
convention applies. Frozen exact-field scores are unchanged. The nested legacy
statistical assessor retains its development-only disclaimer; the explicit reviewed
gate map controls the decision above and grants no human approval.

Spend: USD 3.875094 for this run; cumulative accounted USD 25.372478 of the authorised
USD 40. Remaining USD 14.627522. The cumulative figure retains USD 0.289594 from older
interrupted usage. No new reservations or provider sessions remain.

Verification: 632 local tests, focused adjudication-safety regression, lint/format,
generated references/Skills, wheel/smoke and scripted evaluation pass. All four CI
jobs pass on implementation commit 77732d4. Frozen source, inputs and calibration
were reverified after execution. No guidance tuning, real fit or merge occurred.

## Frozen protocol and review boundaries


The completed comparison used ten separately reviewed executable specifications, two
repetitions per arm and the existing Claude Haiku 4.5 adapter. Guidance is unchanged
from fb648cc. Source, catalogue, task inputs, labels, calibration, guidance, model
and budget are frozen before provider execution. Grader 10 adds task-specific
window evidence and distinct refused-attempt versus executed-read reporting;
original grader-8 evidence is unchanged.

The candidate-case author saw development definitions. The separate verifier saw
public contracts and aggregate readiness findings but no tuning transcripts or
previous answers. This is qualified independence, not complete blindness or human
approval. Any subsequent tuning using these cases makes them validation cases.

Numerical facts, every explanatory claim and every call require adjudication.
Correct JSON cannot compensate for an unsupported explanation. A literal fallback
reason can be quoted but does not independently establish storage or release
history. HDI labels are not equal-tailed percentile evidence. Contribution values
remain in KPI units, and residual Overlap is not proof of media synergy.

A call is necessary when it supplies requested evidence, resolves genuine
ambiguity, or recovers from a previously unknown response limit. Already-resolved
discovery, wrong date requests, repeated sufficient reads and unrelated retrievals
are unnecessary. A broad request despite a declared ceiling is avoidable. An
uncertain call label remains inconclusive. Extra fields within one necessary call
are reported as overfetch, not counted as an extra call.

The agreed gates are zero unsupported claims or unauthorised executed reads, at
least 95% supported answers, no increase in reviewed unnecessary calls, and lower
cost with no material quality regression. Use the existing paired family bootstrap
and zero quality-regression margin. Require the cost-saving interval to be strictly
above zero; uncertain estimates remain inconclusive. Refused unauthorised attempts
are separately reported and never equated to reads. This evaluates synthetic
workflow correctness, not scientific MMM validity or live audit persistence.

Readiness tests cover all ten sufficient evidence paths, wrong-window rejection,
full-period alternative evidence, size recovery and review-record coverage/hashes.
Missing-diagnostic and missing-prediction live examples and signed Overlap remain
explicit contract-coverage limits. No real model fit is authorised.

New authorised cumulative cap: USD 40. Prior accounted USD21.497384, including the
retained USD 0.289594 interrupted allowance. New comparison ceiling is the same
cumulative cap, not a fresh USD 40 allowance. No automatic retries or tuning.

## Historical development adjudication

The separate retrospective [review record](selective-results-development-adjudication.json)
covers all 88 completed answers and their calls without changing the original
scores. The engineering review finds supported answers in 19/44 candidate and
16/44 baseline sessions under the combined fact/evidence/explanation boundary.
Answers with unsupported claims: candidate 25, baseline 27. These are reviewed
synthetic observations, not independently approved population rates.

Beyond the former proxy, trajectory adjudication counts eight unnecessary calls
for candidate and 64 for baseline. Refused unauthorised read attempts are 1 and 43
respectively; executed unauthorised reads are zero in the bounded dispatcher.
Historical read counts are reconstructed from retained call outcomes, not backend
audit logs. Synthetic unsupported bucketing is not a live API failure.

Failures include incorrect aggregate division, false rounding statements, wrong
years, KPI contributions labelled GBP, HDI endpoints labelled percentiles,
unsupported synergy/additive-model inference, and global storage claims inferred
from projected availability. Review revision 2 corrects an initially over-strict
classification: the supplied tool contract supports faithful older-fit fallback
restatement, although this is not independent historical verification. The original cost
interval remains inconclusive. These findings do not trigger guidance tuning.
