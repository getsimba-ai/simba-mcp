# Fresh selective-results acceptance

## Decision: do not merge

The grader-11 run at `b5376cb` was stopped after a reviewer found a sufficient-
evidence defect. Eleven of 32 planned sessions were host-complete. A twelfth
response was received and charged before the checkpoint stop, but its final host
trajectory and grade were not produced. The [evidence record](selective-results-fresh-acceptance-evidence.json)
preserves completed reviews, that partial response and original scores separately.

For the threshold question, the baseline read a saved maximum R-hat of 1.008 and
correctly reported that it fails the supplied strict 1.005 rule. The frozen
fixture required individual `r_hat` rows and wrongly rejected this sufficient
`model_stats` evidence. This was missed in preflight review. Grader 12 now accepts
either valid path; explicit regressions also reject an unrelated read and a
wrong pass judgement. Original grader-11 scores have not been overwritten.

Independent claim review also found a genuine candidate failure in the signed
reconciliation answer. Its arithmetic is correct, but it says a saved timestamp
motivated an unwindowed read. That timestamp only arrived in the response to that
read. This unsupported account of the tool sequence fails the zero-unsupported-
claims requirement independently of the grading defect. Both arms initially
guessed a year omitted from the question; the review records that ambiguity.

The incomplete pairs do not establish lower cost or quality nonregression. No
repaired provider rerun has been made, and no acceptance claim is justified.
Further work must separate factual results from unsupported explanations of the
agent's own actions. If these failures inform another guidance change, this
packet becomes validation material and a new independent acceptance packet is
required.

The interrupted run cost **US$2.614410**. Cumulative accounted spend is
**US$33.065010 of US$40**, including the retained US$0.289594 interrupted allowance.
**US$6.934990 remains**, with no outstanding reservation or provider session.

## Frozen decision protocol

The evidence-grounding guidance passed the [selection readiness check](selective-results-grounding-validation.md).
Guidance and Sonnet settings were frozen before the fresh case packet was opened.
No further guidance tuning is permitted against this packet.

A separate author prepared eight cases across eight declared workflow families
and two synthetic datasets. The author saw development schemas and three
development definitions, but no previous acceptance fixture, provider answers or
tuning guidance. A second agent verified the labels and execution paths after
the configuration freeze. This is qualified independent authorship and review,
not complete blindness or human approval.

Questions and numerical labels stayed unchanged during readiness verification.
Evidence options were corrected to accept valid window summaries, inline marginal
channel identity and complete channel-specific coefficient rows. Grader 11 also
restricts a channel-specific coefficient oracle to the requested channel, while
requiring all relevant periods. Wrong windows and partial rows remain rejected.
All earlier frozen scores remain unchanged.

The comparison uses the existing runner, dispatcher, provider adapter and budget:

- Two repetitions per arm and case, 32 sessions, with alternating arm order.
- Baseline: the original pre-selective results guidance. Candidate: selective
  guidance with the frozen evidence-grounding rule.
- Both arms: `claude-sonnet-5-5`, adaptive thinking, medium effort, 4,096 output
  tokens including thinking, with no temperature override or automatic retry.
- Prior accounted spend US$30.450600, including US$0.289594 retained for older
  interrupted usage. Cumulative cap US$40. No real model fits.
- Independent review of every answer, explanatory claim and call, tied to hashes.
- Zero unsupported claims or unauthorised reads; at least 95% supported answers;
  no increase in unnecessary calls; lower cost without material quality regression.
  Cost and quality intervals crossing the agreed limits remain inconclusive.

The task families are not crossed with both datasets, and some families are
related diagnostic scenarios. Resampled intervals are conditional on this packet,
not guarantees of general reliability. The cases test synthetic workflow and
saved-contract correctness, not scientific MMM validity. Prior live-contract
coverage limits still apply; no new backend or audit verification is claimed.

## Verification and status

The original source passed 520 local tests and all four CI jobs. The corrected
fixture passes 17 focused arithmetic, contract and evidence-path tests. All 524
post-correction local tests pass, along with lint, formatting and generated
guidance/reference checks. PR #58 remains draft and issue #45 remains
open. No merge is authorised until acceptance passes and the owner approves.

Architecture follows [the engineering objective](engineering.md): the fresh
fixture module owns case data, existing result selection owns sufficient evidence,
the host command selects the packet, and experiments owns freeze and assessment.
No duplicate runner or production dependency on evaluation was introduced.
