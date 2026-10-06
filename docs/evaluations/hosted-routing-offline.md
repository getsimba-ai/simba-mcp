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

`routing-selection-v1` contains 120 separately authored public synthetic requests
across the same ten category families. Its labels also remain proposed; development
and selection packets have no identical requests or IDs, but share a development
author and do not establish independent final acceptance. Fresh final acceptance
is not available. Neither generated paraphrases nor the
development packet can be relabelled as an independently authored final holdout.
Version and hash cases before observing outputs; retain original scores and failed
attempts. Any packet used to choose a threshold becomes selection evidence.

## Audit gates

| Gate | Status | Evidence and remaining work |
| --- | --- | --- |
| Fixed non-executable contract | PASS in targeted tests | Documented categories, strict backend envelope and visible-tool intersection |
| Development and selection breadth | PARTIAL | 80 development and 120 separate selection requests cover ten category families; representative production weighting unknown |
| Independent labels | NOT RUN | Distinct recorded reviewer required for verified labels; actual review absent |
| Grader state handling | PASS in regression tests | Correct/wrong, abstention, invalid/missing attempts and unreviewed labels remain distinct |
| Aggregate accounting | PASS in regression tests | Eligible missing/error attempts remain in coverage denominator; unreviewed labels excluded from measured precision |
| Uncertainty | PARTIAL | Wilson intervals for case proportions; complete-task paired uncertainty and confidence reliability not implemented |
| Oracle isolation | PARTIAL | Case contract separates request and labels; provider path must be audited to send request only |
| Trace/version freeze | PARTIAL | Case/result digests and grader version are recorded; prospective campaign/attempt integration outstanding |
| Paid accounting | PASS in synthetic regression tests | Shared host Budget reserves/settles Decisions alongside main-agent work. CLI continuation carries billed failures and unknown reservations, rejects lost prior spend, preserves original reports and skips completed trials. Actual provider billing remains unqualified |
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

The prospective `hosts.routing.RoutingDispatch` calls the real recommendation
handler and configured backend. It does not call OpenAI directly or duplicate
backend admission. Domain execution and grading continue through the existing
fixture dispatch. The adapter checkpoints before submission, records elapsed time
and response digests, and reports unknown usage as missing rather than zero.
Complete-task totals include main-agent cache input and selector input; session
wall time already contains routing, so it is not added twice.

Pricing must be supplied explicitly for the actual organisation, including regional
premiums. The [Decisions guide](https://developers.openai.com/api/docs/guides/decisions),
checked 6 October 2026, lists a base input price of US$0.10 per million and says
regional premiums apply. The ledger rejects a rate below that base. A successful
mock settlement does not verify account pricing or provider access.

## Paired runner configuration

The existing `python -m simba_mcp.evaluation.hosts` entry point accepts
`--routing-comparison`, `--routing-backend-url` and `--routing-input-rate`.
This mode requires `--workflow-suite rlc01`, eager tools and a fixed
`--case-order-seed`. Select the existing Grok model explicitly. Set
`SIMBA_ROUTING_EVAL_API_KEY` for the qualified synthetic backend account and
`XAI_API_KEY` for the main agent. These are environment inputs, never packet
fields. HTTPS origins are required except for loopback HTTP; credentials in URLs
and unrelated comparison protocols are rejected before a report or provider call.

Both arms use the same eager domain tools and synthetic fixtures. The baseline
omits only `recommend_workflow`; the candidate adds the optional advisory tool.
Repetition order alternates arms, while task order uses the frozen seed. The
configuration freezes the backend origin digest, question/version digest, explicit
account price and catalogue policy. Actual adoption is recorded in
`routing_attempts`; exposing the tool does not force its use or imply savings.

Use the existing `--continue-from` and `--continuation-review` protocol after an
interruption, writing a new output. Carry at least the previous ledger's prior,
charged and reserved amounts through `--prior-usd`. A completed workflow trial
uses its own terminal evidence contract; it is not required to contain the
results-only grader fields. Unknown in-flight requests remain charged against the
cap when unfinished trials restart. Reports remain non-accepting until the packet,
grading and independent outcome review gates pass. The 24-task selection packet,
paired uncertainty analysis and actual provider comparison remain outstanding.
