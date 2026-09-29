# Fresh selective-results acceptance

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

## Status

Readiness verified, with 13 focused fixture/path tests passing. Provider comparison
not yet executed. PR #58 remains draft and issue #45 remains open. No merge is
authorised until acceptance passes and the owner approves.

Architecture follows [the engineering objective](engineering.md): the fresh
fixture module owns case data, existing result selection owns sufficient evidence,
the host command selects the packet, and experiments owns freeze and assessment.
No duplicate runner or production dependency on evaluation was introduced.
