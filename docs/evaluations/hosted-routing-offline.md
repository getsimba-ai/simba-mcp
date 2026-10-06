# Hosted routing: offline protocol and audit

Protocol: `hosted-routing-v1`. Question: `workflow-v1`. Grader:
`routing-grader-v1`. This is preparation and contract evidence, not provider or
complete-task acceptance.

## Ownership and primary outcome

Cases and deterministic grading live in `evaluation.routing_cases` and
`evaluation.routing`. Provider execution belongs in the existing host evaluation
entry point and session/budget implementation. There is no second provider runner.
The backend owns production provider execution and distributed admission.

The proposed primary benefit gate is at least 15% lower paired median total input
tokens, including Decisions and every main-agent turn, with no observed task
quality loss, no unintended writes and no more than 5% latency or billed-cost
regression. This gate must be frozen before execution. A latency gate cannot be
chosen retrospectively because token savings failed. Classification accuracy
alone does not pass the complete-task gate.

## Case provenance and split status

`routing-development-v1` contains 80 authored public synthetic intents: eight in
each of eight domains, eight mixed/unclear and eight unsupported. These deliberately
sample boundaries and difficult requests; they are not a population-weighted usage
sample. All labels are proposed, authored by the development agent and not yet
independently reviewed. Their scores remain `NEEDS_REVIEW` even if output matches
the proposed category. Metadata strings in grader test fixtures establish only
mechanical validation, not actual reviewer authorship.

The planned 120-case selection-validation packet is not yet available. Fresh
final acceptance is also not available. Neither generated paraphrases nor the
development packet can be relabelled as an independently authored final holdout.
Version and hash cases before observing outputs; retain original scores and failed
attempts. Any packet used to choose a threshold becomes selection evidence.

## Audit gates

| Gate | Status | Evidence and remaining work |
| --- | --- | --- |
| Fixed non-executable contract | PASS in targeted tests | Documented categories, strict backend envelope and visible-tool intersection |
| Development breadth | PARTIAL | 80 distinct authored requests cover ten category families; representative production weighting unknown |
| Independent labels | NOT RUN | Distinct recorded reviewer required for verified labels; actual review absent |
| Grader state handling | PASS in regression tests | Correct/wrong, abstention, invalid/missing attempts and unreviewed labels remain distinct |
| Aggregate accounting | PASS in regression tests | Eligible missing/error attempts remain in coverage denominator; unreviewed labels excluded from measured precision |
| Uncertainty | PARTIAL | Wilson intervals for case proportions; complete-task paired uncertainty and confidence reliability not implemented |
| Oracle isolation | PARTIAL | Case contract separates request and labels; provider path must be audited to send request only |
| Trace/version freeze | PARTIAL | Case/result digests and grader version are recorded; prospective campaign/attempt integration outstanding |
| Paid accounting | PARTIAL | Production unknown charges retain Redis reservations; cumulative evaluation ledger needs Decisions integration |
| External provider qualification | NOT RUN | Account access, actual schema/usage and latency not tested |
| Paired complete tasks | NOT RUN | Planned 24 tasks, three repetitions per arm; main model, profile, fixtures and cache conditions held fixed |
| Named-client acceptance | NOT RUN | Package, deployment, actual adoption and fallback behaviour require observed evidence |

The scorer's confidence is never an authority signal. Review ambiguous development
labels against the rubric, especially priors versus modelling, campaign versus
aggregate reporting and adversarial category overrides. Alternative sufficient
categories may be listed where justified before freezing the packet.

## Resumption and spend

Prepare the source candidate, label-review packet, calibration report and trace
format before any paid comparison. The proposed US$25 cumulative cap is pending
authorisation. Carry billed failures and unknown charges across attempts and
protocol versions. No provider or model expansion is implied by this protocol.
Synthetic successful routing does not establish scientific validity, publication,
deployment or complete-task improvement.
