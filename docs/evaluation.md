# Workflow contract evaluations

Run the deterministic suite from an installed checkout:

```sh
python -m simba_mcp.evaluation --samples 3 --output-dir .codex/evaluation
```

This writes `evaluation.json` and `evaluation.md`, returning a nonzero exit code
when a contract assertion fails. No credentials, sockets, model-provider calls,
live backend writes or fits are used. Synthetic mutation requests exist only
inside an HTTPX mock transport. The real MCP SDK dispatch, public tool functions
and API request adapter are exercised. Scripts select the tools; no agent selects
them. This suite establishes contract behaviour, not agent task success or
scientific recovery.

## Cases and grading

The versioned source manifest is `src/simba_mcp/evaluation_cases.py`. Each case
declares its tool arguments, allowed HTTP request sequence, synthetic responses,
independent expected result fields and refusal/cancellation outcome. Request
bodies and query strings are checked exactly. Result dictionaries permit additive
fields, while asserted scalar values, lists, units and identifiers remain exact.
Unexpected writes, request mismatches and unconsumed expected requests fail.

| Case | Contract covered |
| --- | --- |
| analyse_model | Status then results, exact activity keys, units, intervals, distinct ROI and contribution fields |
| create_mmm | Requested sampler and column settings, one creation then status |
| advanced_priors | Explicit channel priors forwarded unchanged |
| optimiser_setup | Currency budget, percentage bounds, period arrays and profit objective |
| draft_edit | Creation and versioned update preserve nested authoring fields; no implicit publication/fit |
| study_review | Unevaluated evidence stays unevaluated; no write |
| stale_revision | Publication refusal remains an error, without retry or launch |
| wrong_channel | Unknown-channel backend refusal remains an error |
| rate_limit / outage | Read recovery and bounded retry exhaustion |
| uncertain_launch | No automatic mutation replay; scripted explicit recovery retains the same submission key |
| cancellation | Injected cancellation propagates without another request |
| invalid_arguments | Typed argument refusal before backend I/O |
| missing_capability | Unsupported control priors never create a model |

Tests deliberately break every case's expected outcome. Separate tests alter a
request setting and turn missing evidence into a pass, proving those regressions
are detected. The review case checks evidence transport only: it does not grade a
model's analytical prose or establish that a real holdout was completed.

## Measurements

Reports include source/package versions, fixture digest, case/repetition,
individual assertions, call and attempt counts, elapsed time and separately named
backend decoded/downloaded and serialised tool-result byte counts. No request
arguments, credentials or raw tool results appear in reports.

Timing includes instrumentation, dispatch, real retry delays and client closure;
fixture/client setup is excluded. First and subsequent repetitions use a shared
process but fresh clients. These are not cold-network or production timings.
Small-sample percentiles are descriptive. Provider usage, model turns and MCP
transport framing bytes are null with an explicit reason. Zero discovery calls
means the script invokes tools directly, not that an agent discovered them for
free. Use `simba_mcp.performance` for actual catalogue measurements and
`simba_mcp.benchmark` for instrumentation overhead comparisons.

## Optional host-side evidence

`simba_mcp.evaluation_reports.HostTrial` defines a separate versioned host report:

```python
import json
from simba_mcp.evaluation_reports import HostTrial

trial = HostTrial.model_validate(json.loads(report_text))
schema = HostTrial.model_json_schema()
```

Hosts record their model/version, fixture and configuration digests, cache
condition, repetition, assertion outcomes, unintended writes, calls, turns,
discovery, attempts, payload representation, timing and actual provider usage.
Missing measurements require reasons. Provider usage declares whether input
tokens include cached input. Tokenizer estimates are not provider usage.
Unsupported configurations must be `untested`; missing assertions or unintended
writes cannot pass. Schema validation checks consistency, not evidence authenticity
or completeness of the host's graders. Consumers must independently verify case
coverage and the underlying results. Never interpret these checks as certification.

## Remaining acceptance

No model trials or numerical budgets are established by this command. Repeated
model-assisted evaluation needs explicit spend limits and reliable graders,
including failure when required holdout evidence is absent and correct distinction
between contribution and return on spend. Maintain human authority over final
acceptance. Unsupported modes remain untested.

PERF-02 (#40) remains open until baseline model evidence and a maintainer-approved
budget decision exist. A budget record must identify baseline versions, cases,
sample counts/variation, metric definitions, proposed tolerances, rationale,
approver and review conditions. No thresholds are invented by this suite.
Comparisons of future compact/discovery implementations run under #50 after those
implementations exist. No runtime default changes here.
