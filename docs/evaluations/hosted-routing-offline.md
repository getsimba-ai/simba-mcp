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
| Uncertainty | PARTIAL | Wilson classification intervals, fixed confidence-band observed accuracy and descriptive family-clustered paired task bootstrap exist; actual confidence reliability and live uncertainty remain unqualified |
| Oracle isolation | PASS offline | Classification mode passes only request text into the real MCP handler. Mock transport verifies exact backend body; backend ProviderPool constructs only model/input/trusted questions, with its separate provider credential |
| Trace/version freeze | PASS offline | Classification packets, question, source, calibration and price are frozen before any client opens; shared adapter checkpoints before submission; campaign lineage retains exact report hashes |
| Paid accounting | PASS in synthetic regression tests | Shared host Budget reserves/settles Decisions alongside main-agent work. CLI continuation carries billed failures and unknown reservations, rejects lost prior spend, preserves original reports and skips completed trials. Actual provider billing remains unqualified |
| External provider qualification | NOT RUN | Account access, actual schema/usage and latency not tested |
| Paired complete tasks | NOT RUN | Frozen public 24-task selection packet and reporter pass offline checks; three repetitions per arm and actual providers remain unrun |
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

## Classification mode and review packet

The existing host entry point supports an offline packet without opening provider
or backend clients:

```sh
python -m simba_mcp.evaluation.hosts --routing-classification development \
  --routing-dry-run --samples 1 --cap-usd 0 --output development-not-run.json
```

Use `selection_validation` for the separate 120-case packet. Every case remains
`NOT_RUN`; proposed labels do not turn into measured correctness. Do not overwrite
these reports or claim their mechanical generation qualifies a provider.

Network mode requires an explicit `--routing-label-packet` containing a complete
JSON list of reviewed `RoutingCase` objects and `--routing-calibration-review`.
The review object has exactly `passed`, `reviewer`, `packet_sha256`,
`grader_version` and `rationale`. Its packet digest is `fingerprint` of the
validated case list; reviewer identity must be distinct from all case authors.
Every case records verified label status and a distinct reviewer. These are
recorded review assertions, not proof that review happened. Test fixture reviewer
strings never count as actual review. Actual label and grader review remain pending.

Keep `--samples 1`: repeated attempts are not independent classification cases.
Supply the qualified backend origin, explicit account price and existing backend
key environment input. Classification shares the existing Budget and real MCP
handler/backend adapter; it does not open a main-agent model or call OpenAI directly.
No label, expected choice, author or rationale is sent to the backend. The backend
pool's body contains only model, submitted text and the trusted fixed question.
Network mode spaces submissions by at least 6.1 seconds for default account
admission, rather than exhausting the ten-per-minute limit. It never retries an
attempt automatically. Stop files are checked before new submissions. Interrupted
attempts retain reservations and `EXECUTION_ERROR`; later unsubmitted cases remain
`NOT_RUN`. Classification continuation is not implemented: a new campaign must
carry previous charged and reserved spend explicitly and retain the original report.

The summary retains precision/coverage Wilson intervals, category confusions and
ten fixed confidence bands with mean confidence and observed accuracy intervals.
Alternative sufficient labels remain a set. Unreviewed labels, missing attempts
and execution errors cannot populate accuracy bins. The provider documents a
separate confidence field alongside option probabilities, so these are observed
score bands, not multiclass probability calibration. The backend omits confidence
on abstention, which limits this analysis to returned classifications. It cannot
establish calibration below the deployed threshold or tune that threshold from
unobserved scores. See the [answer interpretation guidance](https://developers.openai.com/api/docs/guides/decisions#interpret-the-answers), checked 6 October 2026.

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
grading and independent outcome review gates pass. A continuation report that
omits earlier completed trials reports missing pairs; it cannot establish a saving
from the resumed subset. Combine the ordered hash-bound campaign evidence with:

```sh
python -m simba_mcp.evaluation.hosts.routing_report \
  --report original.json --report continued.json --output campaign.json
```

This reporting command makes no provider calls and refuses to overwrite output.
Supply every report in chronological order, starting with the original. It checks
frozen inputs/calibration, identical protocol, source-transition review bindings,
exact predecessor file hashes, completed trial identities and carried spending.
All interrupted attempts remain in the campaign ledger, attempt outcomes and
measurements. Completed tasks cannot be repeated under a new report. Unknown
attempt usage keeps the cumulative reservation and prevents a paired saving;
restarting successfully cannot erase it. Missing main-agent billing also remains
unknown rather than becoming zero cost. Scores and original files are preserved.

## Frozen task selection and reporting

The packet is `docs/evaluations/packets/routing-task-selection-v1.json`, SHA-256
`926cd3d610ccb16f602bfcd222a3538b244299d45d622a2215ee96e937aa2cab`.
Use it with `--workflow-packet` alongside the routing flags. Three repetitions
produce 144 main-agent sessions before any interrupted attempts. This is a public
synthetic selection packet, assembled by the development agent from current
role workflows, RLC tasks and the explicit prior-settings contract, with one new
saved-VAR-failure read. It is neither independently authored nor a final holdout.
Expected facts are frozen before provider execution; independent label and prose
review remain unperformed. No customer records are included.

| Family | Tasks |
| --- | --- |
| Reporting | 2 |
| Campaigns | 8 |
| Results | 4 |
| Optimiser | 3 |
| Studies | 3 |
| MMM | 1 |
| Priors | 1 |
| VAR | 1 |
| Mixed | 1 |

These counts cover boundaries and recovery, not production frequency. Single-case
families provide weak generalisation evidence. Some fixtures explicitly permit a
synthetic creation or state change; the router itself cannot execute it. Task
contracts separately assert that no unintended write occurs. Existing result
fixture objects are copied into the packet so later source defaults cannot change
the frozen evidence. All workflow contracts execute through the real MCP handler
and strict mocked HTTP exchanges. Result grading remains under its existing owner.

`hosts.routing_report` records each arm's expected/observed trial counts, outcome
states, pending claim reviews, routing adoption/reasons, unknown accounting and
p50/p95 observed latency, tokens and cost. Complete paired evidence produces
selector-inclusive savings estimates; missing, duplicated, non-finite, unknown or
unfinished trials prevent those estimates. Quality comparison is withheld while
explanatory claims await review. Public reports always have `accepted: false`.

Paired uncertainty uses a fixed-seed bootstrap over families, with repetitions
resampled as pairs within each task. Task means are averaged within families;
savings compare medians of those family measurements. Each family has equal
weight, rather than allowing eight campaign tasks to dominate the estimate.
The arm p50/p95 values are separately labelled descriptive session statistics.
One family cannot produce an independence interval, and synthetic intervals do
not establish scientific validity or production non-inferiority. The paired
quality and efficiency thresholds still require prospective owner agreement.
