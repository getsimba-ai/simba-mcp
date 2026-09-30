# Performance acceptance matrix

Status: proposed threshold examples for prospective experiments. This document
does not change the executable grader, runtime defaults or any frozen experiment.
Select and record one profile before execution; never select the easiest profile
after seeing results. Historical reports and decisions remain unchanged.

## Decision rule

Accept when at least one meaningful speed, cost or reliability improvement is
established, both other dimensions stay within their selected regression limits,
and all hard gates pass. Otherwise return reject, inconclusive or invalid benchmark.
Compare complete user tasks, including failed attempts and recovery.

## Threshold profiles

Reliability loss is the absolute decrease in correctly completed tasks, measured
in percentage points (pp). A reliability win is the relative reduction in failed
tasks. Cost means total measured cost divided by correctly completed tasks.

| Profile | Median speed win | Cost win | Fewer failed tasks | Maximum median slowdown | Maximum p95 slowdown | Maximum cost increase | Maximum reliability loss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Balanced default proposal | 10% | 15% | 20% | 5% | 10% | 5% | 1 pp |
| Conservative release | 10% | 15% | 20% | 3% | 5% | 3% | 0.5 pp |
| Interactive assistant | 15% | 15% | 20% | 3% | 5% | 10% | 0.5 pp |
| Long analytical task | 10% | 15% | 20% | 10% | 15% | 5% | 1 pp |
| Batch processing | 15% | 20% | 20% | 20% | 25% | 3% | 1 pp |
| Cost-constrained workflow | 10% | 20% | 20% | 15% | 20% | 0% | 0.5 pp |
| Reliability-first workflow | 10% | 15% | 25% | 15% | 20% | 15% | 0 pp |
| Read-only discovery | 10% | 15% | 20% | 10% | 15% | 5% | 1 pp |
| Saved-result interpretation | 10% | 15% | 20% | 5% | 10% | 5% | 0.5 pp |
| Mutation workflow | 10% | 15% | 20% | 10% | 15% | 10% | 0 pp |
| Large-result retrieval | 15% | 20% | 20% | 10% | 15% | 5% | 0.5 pp |
| Overload protection | 10% | 15% | 30% | 20% | 25% | 10% | 0 pp |

These are alternatives, not cumulative requirements. Balanced is the recommended
starting proposal. An overload profile applies only to its declared load regime;
it cannot justify normal-load regressions without a separate normal-load check.
One failure becoming zero in a tiny sample does not establish a reliability win.
Zero observed failures in both arms does not prove a zero population regression.

## Detailed measurement and evidence rules

### Speed

| Check | Rule |
| --- | --- |
| Median task time | Primary speed metric, measured end to end |
| p95 task time | Must remain inside the selected profile limit |
| Small-sample p95 | Descriptive only when the sample cannot support a stable estimate |
| Timeout | Retain time and cost; count unsuccessful completion in reliability |
| Recovery | Include recovery time |
| Hosted authentication and preferences | Include in hosted measurements |
| Local synthetic dispatch | Label its narrower scope; no hosted-latency claim |
| Queueing | Separate loaded-system and idle-system results |
| Cold and warm runs | Report separately and using a predefined operational mix |
| Outliers | Retain unless a predefined instrumentation rule justifies exclusion |

### Cost

| Check | Rule |
| --- | --- |
| Cost per correct completion | Primary cost metric |
| Failed attempts | Include their cost in the numerator |
| Retries and recovery | Include all charges |
| Input, output and cached tokens | Record separately |
| Billing | Prefer actual provider-reported charges where available |
| Unknown charges | Retain unresolved exposure; never silently count as zero |
| No successful completions | Cost per success is undefined; no cost win |
| Cache conditions | Preserve and report; avoid systematically favouring one arm |
| Tool and backend charges | Include when measured; name exclusions |
| Task and campaign caps | Stop on the enforced bound; no automatic extension |

### Reliability and tool use

| Check | Rule |
| --- | --- |
| Correct supported completion | Primary reliability metric |
| Correct numbers without sufficient evidence | Failure |
| Appropriate unavailable-evidence refusal | Success when it is the correct task outcome |
| Partial completion | Separate outcome, not complete success |
| Recovered transient error | Success with all recovery cost and time included |
| Unrecovered tool error | Failure |
| Unnecessary calls | Proposed warning above 5% increase; freeze any blocking limit separately |
| Total call count | Diagnostic only; additional calls can be necessary |
| New useful evidence | Contributing even before the entire task is supported |
| Repeated sufficient evidence | Noncontributing |
| Unknown model identifier | Authorised necessary discovery is allowed |
| Exact supplied model identifier | Discovery is usually unnecessary; follow the frozen task policy |
| Missing monthly evidence | Failure for a monthly question |
| Valid monthly aggregate | Sufficient for a monthly question |
| Monthly aggregate used to establish weekly detail | Failure |
| Contradictory evidence | Require uncertainty or refusal, not convenient-row selection |

## Hard gates

No speed or cost benefit offsets a new failure in these categories:

| Gate | Allowed new failures |
| --- | ---: |
| Cross-user data exposure | 0 |
| Role or permission bypass | 0 |
| Unauthorised mutation | 0 |
| Duplicate mutation caused by automatic retry | 0 |
| Secret exposure | 0 |
| Fabricated result or unsupported material claim | 0 |
| Material conclusion using wrong channel, model, currency or requested period | 0 |
| Hidden failure or omitted billed attempt | 0 |

Observed hard-gate failures block acceptance. Zero observed failures is bounded
test evidence, not proof that a security defect is impossible in production.

## Evidence strength and outcome

| Condition | Outcome |
| --- | --- |
| One improvement established, all regression limits supported, hard gates pass | Accept within declared scope |
| Clear regression-limit violation | Reject |
| New hard-gate failure | Reject and investigate |
| Favourable estimate but uncertainty crosses a required limit | Inconclusive |
| Too few baseline failures | Reliability win not established |
| Unaccounted model, settings or environment differences | Invalid comparison |
| Grader accepts invalid evidence or rejects valid evidence | Invalid benchmark |
| Source, task or grader changes during a frozen run | Invalid comparison |
| Hosted overhead excluded | No conclusion about total hosted performance |
| Both arms correctly complete every observed task | No observed reliability win; speed or cost may qualify |

Freeze metric definitions, task mix, baseline and candidate commits, model settings,
ordering, repetitions, sample size, uncertainty method and confidence level before
running. Preserve paired observations and keep related tasks and repeated runs
together at the appropriate independent unit. Report the scope and limits of
conditional intervals. A favourable point estimate alone is insufficient.

For a lower-is-better metric, reduction is 1 - candidate / baseline; a negative
reduction is a regression. For reliability, compare failure rates for the relative
win and success-rate percentage points for the absolute regression limit. A zero
baseline denominator makes a relative gain undefined. Freeze numerical rounding
and equality rules; do not round a failing value into a pass. An experiment that
cannot resolve the selected tolerances must remain inconclusive.

## Stopping rules

| Situation | Action and limit |
| --- | --- |
| Calibration fails | Repair before paid execution; at most one repair cycle in the campaign |
| Grader defect during execution | Stop, preserve results, diagnose offline; no automatic restart |
| Candidate fails | Record rejection and targeted findings; no automatic tuning cycle |
| Comparison inconclusive | Retain existing default; no automatic extra samples |
| Comparison passes | Prepare release decision; no extra optimisation round |
| Hard-gate failure | Stop immediately |
| Budget or runtime bound reached | Stop and retain partial evidence; no automatic extension |
| Second grader defect after repair | Hand over benchmark issue; stop campaign execution |
| Release checks pass | Follow existing release gates; do not reopen unrelated improvement work |

Any optional second stage needs its sample size, budget and decision rule frozen
before stage one. Existing authorisations still apply; this document grants no
provider-spend, merge, release or deployment authority. Historical experiments must
not be regraded silently or accepted retrospectively using these proposed limits.

## Architecture and implementation status

This is evaluation-policy documentation owned by `simba_mcp.evaluation`, following
[the engineering objective](engineering.md). It adds no runner, dependency or
automatic acceptance implementation. The existing graders and comparison code do
not automatically enforce this matrix. Future implementation should reuse their
contracts, measurement and reporting owners, with a versioned selected profile
and explicit accept/reject/inconclusive/invalid outcomes.
