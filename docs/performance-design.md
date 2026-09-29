# Performance measurement and evaluation design

Reviewed 29 September 2026 against `03dd97b570ffa23de260aabe404d4382789f5d41`.
Scope: [PERF-01 / #39](https://github.com/getsimba-ai/simba-mcp/issues/39) and the
handover to [PERF-02 / #40](https://github.com/getsimba-ai/simba-mcp/issues/40), within
[epic #38](https://github.com/getsimba-ai/simba-mcp/issues/38).

## Recommendation

Measure the current catalogue and request path before selecting optimisations.
Add an offline report of the actual HTTP MCP `initialize` and `tools/list` responses,
plus optional aggregate observations around the existing tool, HTTP and results
boundaries. Preserve the tool catalogue, credentials, response envelopes and retry
rules. Build workflow evaluations on the resulting measurements in PERF-02.

The strongest tradeoff is measurement overhead: counting serialised results needs
additional serialisation when enabled. Keep this opt-in, measure its cost, distinguish
measurement time from handler time, and never infer production latency from a mock
backend. No numerical speedup or model-quality threshold has been established.

## Evidence and current system

| Claim | Status and evidence | Consequence |
| --- | --- | --- |
| The composition root registers 80 tools and exposes instructions | Observed locally: `server.py:TOOLS`, `mcp`; `reference.py:current` | Read live SDK output; do not count characters in source files |
| Hosted requests share one HTTP pool, while credentials use a ContextVar | Observed locally: `runtime.py:app_lifespan`, `auth.py:_client`, `api_client.py:CALLER_API_KEY` | Observations must be task-local and contain no caller identity |
| GET/HEAD can retry; writes default to one attempt | Observed locally: `SimbaAPIClient._request` | Observe every attempt without changing replay or recovery semantics |
| The results byte cap is after download and filtering | Observed locally at the PERF-09 baseline; this branch adds earlier optional transport ceilings | Keep encoded body, decoded body, selected payload and MCP representation separate |
| SDK tracing already exists and is inert without a configured OTel SDK | Documented: SDK OpenTelemetry guide; observed dependency `opentelemetry-api` | Do not install a tracing service or duplicate its transport implementation |
| HTTPX response hooks run before the body is necessarily consumed | Documented: HTTPX event-hooks guide | Observe after the existing awaited request; do not read the body in a hook |
| A smaller catalogue improves this application's task performance | Unverified | Requires repeated host/model trials in PERF-02 and later comparisons |

```mermaid
flowchart LR
  H[Host: tool selection and model usage] -->|MCP JSON-RPC over stdio or HTTP| S[SimbaMCPServer: argument validation and result conversion]
  S -->|Python async call| D[Domain tool: forwarding and local result selection]
  D -->|Python async call| C[SimbaAPIClient: caller credentials, pool and retries]
  C -->|HTTPS: caller bearer token and request| B[Backend: authorisation, durable state and scientific evidence]
  B -->|HTTP response body| C
  C -->|Parsed response| D
  D -->|Result or refusal| S
  S -->|MCP result| H
```

The host owns discovery, model prompting and model token accounting. MCP executes
tools; it cannot establish what definitions a host actually sent to a model.
Backend validation and durable workflow state remain authoritative.

## Alternatives and decision ledger

| Decision | Choice and rationale | Alternative and reconsideration trigger |
| --- | --- | --- |
| D-003 | Reuse the existing subclass `call_tool` and HTTP request loop for observations; use public result types | SDK middleware is documented as provisional in v2. Consider it if stable supported hooks supply the missing measurements across the supported SDK range |
| D-004 | Local report from actual ASGI HTTP responses; retain registration order and a digest of each measured representation | Calling `mcp.list_tools()` alone misses the JSON-RPC envelope. A remote report introduces access and customer-data risks with no benefit for this catalogue baseline |
| D-005 | Default disabled. A per-invocation ContextVar records bounded numbers and fixed labels; optional JSON-lines stderr sink or an in-process callable | An OTel exporter can be added later if operationally required. It does not replace the report or provide host usage |
| D-006 | Explicit allowlisted route templates; unknown routes and tools use `other` | Guessing identifiers with regular-expression redaction can leak names. A new route requires an explicit template if separate attribution is needed |
| D-007 | Optional named tokenizer, recording package version and encoding. No model-to-tokenizer guess | Bytes-only mode remains available without tokenizer assets. Encoded JSON token counts are representation estimates, never billing or actual host input |

These are implementation choices within the requested scope, not approved performance
budgets. Earlier conversational calendar estimates were rough judgements and provide
no acceptance evidence or delivery commitment.

## Proposed measurement boundaries

```mermaid
flowchart LR
  R[Offline report process] -->|In-memory HTTP JSON-RPC: initialise and list tools only| A[Existing ASGI app]
  A -->|Exact HTTP response bytes| R
  R -->|Sizes, hashes, versions and optional token estimates| F[Local JSON and Markdown reports]
  T[Existing tool call] -->|Fixed tool name and numeric observations via task-local state| O[Optional collector]
  Q[Existing HTTP attempt] -->|Template, status, elapsed time and body byte counts| O
  P[Existing results processing] -->|Filtering and byte-cap serialisation durations| O
  O -->|Bounded numeric event, never arguments or bodies| E[Configured local sink]
```

| Measurement | Definition and limitation |
| --- | --- |
| Catalogue envelope | Exact UTF-8 bytes of the local HTTP JSON-RPC `tools/list` response, with fixed request ID; excludes HTTP headers and compression |
| Instructions | Instructions from the actual initialise response, measured as a JSON string separately from the catalogue |
| Tool and field sizes | Compact UTF-8 JSON representation in returned registration/key order. Field token counts are independent and are not additive |
| Tool duration | `call_tool` validation, handler and SDK conversion; excludes transport delivery and the final metric sink |
| HTTP attempt | Existing `client.request` duration through complete body read; every attempted request counts, including retryable responses and transport failures; backoff belongs to total tool duration |
| Downloaded body bytes | HTTPX `num_bytes_downloaded`, before content decoding; excludes headers/TLS. Prebuffered test responses can have unavailable raw counts |
| Decoded body bytes | Length of the fully read `response.content`; no raw body exported |
| Parsing/filtering | Time in `_parse_response` and in existing result filtering respectively |
| Tool result representation | Content array and whole CallToolResult serialised separately, including structured/text duplication; excludes JSON-RPC envelope and transport framing |
| Measurement serialisation | Additional time spent obtaining result byte counts; separately reported, not labelled SDK serialisation time |
| Provider usage | Unavailable in PERF-01. PERF-02 must obtain actual input/cached-input/output usage from the selected host and record missing values explicitly |

No URL, header, query parameter, argument, body, exception message, model/study/project
identifier or correlation ID reaches the sink. Result values are serialised only to
count bytes and then discarded. Observation failures do not change the tool result.
Bound attempt detail per tool call and expose a dropped-detail count if exceeded.
An optional sink is trusted application code and must be prompt and non-blocking;
stderr can block if the surrounding process stops consuming it.

## Normal and interrupted calls

1. Choose the configured sink once. With no sink, follow the existing call directly.
2. With observations enabled, install a fresh task-local collector and validate the
   tool label against the registered catalogue. Preserve the caller credential path.
3. Record each HTTP attempt, then parsing and any local result processing. Backend
   errors still use `api_error` and `_wire_errors`; invalid arguments still use
   `_argument_refusal`.
4. After SDK conversion, count serialised result representations. Emit only numeric
   values and fixed labels, then reset the ContextVar in a `finally` path.
5. On cancellation, record cancellation and re-raise it. An in-flight failed HTTP
   request has unknown body byte counts. Cancellation during retry backoff belongs
   to the tool observation, not a second HTTP attempt. Never infer backend job
   cancellation or replay a mutation. Sink errors must not replace cancellation.

Concurrent calls must have separate collectors even when they share the connection
pool. There is no telemetry store to recover, no new business-state cache, no retry
queue and no new durable identifiers.

## PERF-09 response download bounds

`SimbaAPIClient` now reads response bodies from an HTTPX stream, counts encoded
bytes, and parses only after the complete body has passed the configured ceilings.
For gzip and deflate responses it also bounds decoded bytes while decompressing.
The existing `max_response_bytes` results option remains a later cap on the
selected MCP result and its serialised content; it does not replace transport
limits or include the full HTTP envelope.

Set `SIMBA_API_MAX_ENCODED_BYTES` and `SIMBA_API_MAX_DECODED_BYTES` to positive
integer byte counts to enable transport limits. If only one is set, the same
ceiling applies to both encoded and decoded representations. Empty or unset values
leave the existing full-result download path uncapped for compatibility. This is
an opt-in, reversible rollout because production response-size baselines and an
approved default ceiling are not yet available. Invalid values fail startup with
a configuration error. With limits enabled, the client negotiates gzip and
deflate and accepts both zlib-wrapped and raw deflate. With limits unset, HTTPX
retains its normal compression negotiation and decoding. The bounded path refuses
unsupported encodings and stacked or concatenated compressed streams with a
structured error and no partial data until their bounded decoding is covered by
a tested implementation.

An encoded ceiling counts response entity bytes yielded by HTTPX after transfer
framing and before content decompression. A decoded ceiling counts bytes supplied
to JSON or CSV parsing. `Content-Length` is used only for early refusal when it
exceeds the configured encoded ceiling; streamed bytes remain authoritative. The
MCP envelope and host-side token usage are separate measurements. No numerical
ceiling is recommended until operators review representative result sizes and
the baseline in PERF-09.

Accepted bodies still need memory for buffering and parsing. Synthetic JSON
containing one long string at decoded ceilings of 256 KiB, 1 MiB and 4 MiB peaked
at approximately three times the decoded size in Python allocation tracing, for
both identity and gzip responses. This is evidence for those shapes only, not a
process RSS or concurrent-request bound. Object-heavy JSON and representative
production response sizes still need measurement before approving defaults.

## Implementation and acceptance

| Milestone | Paths and ownership | Required evidence | Rollback |
| --- | --- | --- | --- |
| Surface report | New `performance.py`; reuse app construction and SDK wire response | JSON/Markdown, actual field names and order, reproducible digest, versions, current revision and dirty state; absent token counts explicit | Remove optional command; server catalogue unaffected |
| Optional observations | New `telemetry.py`; `server.py`, `api_client.py`, `tools/results.py` | Disabled/enabled wire equivalence; fixed label privacy checks; retry, malformed-body, transport, cancellation, validation and caller-isolation tests | Unset `SIMBA_MCP_METRICS`; default remains off |
| Synthetic baseline | Versioned local fixture and optional benchmark command | First iteration and warm sample distribution, fixture digest, platform/dependency provenance, enabled vs disabled overhead; no live backend | Regenerate on a named revision; preserve previous evidence |
| Release checks | Existing CI, supported SDK floor and package build | Input-schema snapshot, generated-reference drift, full suite and lint/format; exact tested head | Revert the measurement change |
| PERF-02 handover | Follow-up issue #40 | Schema below and deterministic fixtures before paid/live work; budgets awaiting evidence and maintainer decision | Keep baseline behaviour and skip unsupported configurations |

## PERF-02 handover

Use a versioned case manifest with: case ID, task prompt, synthetic backend fixtures,
allowed and forbidden writes, expected fields/units/intervals/exact channel keys,
recovery requirements and deterministic assertion IDs. Initially cover existing
model analysis, simple MMM creation, advanced priors, optimiser setup, study
authoring/editing and study review.

Record a run as `{case_id, fixture_digest, revision, configuration, host_version,
model, repetition, cache_condition, correctness, unintended_writes, tool_turns,
discovery_calls, backend_attempts, payload_bytes, latency_seconds, usage}`. Missing
usage fields are null with a reason, never zero. Record model/provider versions and
sampling settings from the actual runner; no provider is chosen by this design.

Offline contract fixtures come first and require no credentials or backend fits.
Then use a host-side model evaluation with recorded spend limits and the versioned
[evaluation report contract](evaluation.md). The MCP package provides deterministic
contract checks; it does not own model orchestration or scientific grading.
Live fits and backend writes require separate authorisation. Compare the baseline
to a candidate only when that candidate exists; an unimplemented mode is untested.
PERF-02 establishes the baseline and budget decision. PERF-12 (#50) executes the
comparison matrix for subsequent compact/discovery implementations.

Hard gates: zero unintended writes, unchanged deterministic contracts and no loss
of scientific evidence. Numerical latency/token budgets and stochastic quality
tolerances remain pending until baseline sample counts and variation are available.
Do not close #40 on deterministic tests alone.

## Source register

All pages checked 29 September 2026. Dates here are retrieval dates, not publication
dates. Inspect installed source and test the SDK floor when docs differ.

- [MCP Python SDK v2](https://py.sdk.modelcontextprotocol.io/v2/): public server APIs and transports. Project constraint `mcp>=2.1,<3`; initial isolated test environment resolves 2.2.0.
- [SDK middleware](https://py.sdk.modelcontextprotocol.io/v2/advanced/middleware/): observation hooks are provisional within v2. Existing `SimbaMCPServer.call_tool` is reused instead.
- [SDK OpenTelemetry](https://py.sdk.modelcontextprotocol.io/v2/run/opentelemetry/): built-in message spans; API dependency is inert without a configured SDK. These spans do not supply Simba backend payload accounting.
- [HTTPX event hooks](https://www.python-httpx.org/advanced/event-hooks/): response hook runs before required body consumption. Project floor 0.27; inspected 0.28.1.
- [HTTPX download accounting](https://www.python-httpx.org/advanced/clients/#monitoring-download-progress): raw downloaded body bytes differ from decoded content when compressed.
- [tiktoken source](https://github.com/openai/tiktoken): named encodings and `get_encoding`; use only as an optional representation counter, not provider billing.

Observed results and SDK-floor verification are recorded in the
[initial baseline](performance-baseline.md). PERF-02 host selection, model trials
and budget approval remain pending. A successful local report establishes neither
host support for deferred discovery nor production performance.

## Opt-in request budgets and admission (issue 48)

The shared API client owns one admission queue and request budget, in accordance
with `docs/engineering.md`. `request_budget.py` owns only configuration, deadline
arithmetic and admission primitives; it does not dispatch tools, cache results or
schedule backend jobs. Runtime constructs the policy once for its shared client.

Set `SIMBA_API_REQUEST_POLICY_JSON` to a JSON object with all of these fields:
`total_seconds`, `connect_seconds`, `read_seconds`, `write_seconds`,
`pool_seconds`, `max_active`, `max_active_per_caller`, `max_queued` and
`max_queued_per_caller`. Durations must be finite and positive; active limits are
positive integers; queue limits can be zero to refuse waiting. Caller ceilings
cannot exceed process ceilings. Optional `operation_seconds` overrides totals for
`read`, `write` and `upload`; upload means POST `/api/v1/ingest`. Values must be
selected from capacity measurements. No production values are prescribed here.
Unset or empty configuration preserves the existing timeout and retry behaviour.
Invalid configuration fails startup. Removing the setting and restarting restores
the previous behaviour.

With a policy enabled, the monotonic total includes admission waiting, all HTTP
attempts, parsing and retry sleeps. Phase timeouts are capped by the remaining
budget. Only existing retry-eligible reads retry. Backoff uses full jitter;
Retry-After integer seconds and HTTP dates are honoured as a minimum delay. A
retry is refused if that delay consumes the remaining budget. Each next attempt
is clipped to the remaining budget, rather than receiving a new total allowance.
A successful return is checked against the budget after parsing as well.

Admission limits active operations and queued calls for the shared process client
and each credential identity. Active operations retain their permit during
backoff. Oldest eligible queued callers proceed first, so a saturated caller does
not block another eligible caller. Identities are keyed digests with a random
process-local secret, retained only while in use and never emitted in telemetry.
They isolate credential generations, not people: different valid keys belonging
to one person are distinct caller identities. No authentication or backend
permission is inferred from admission. Multiple worker processes have separate
limits; deployment capacity must account for their aggregate.

A full queue returns structured 429 `request_overloaded` without sending. Overall
expiry returns structured 504 `request_deadline_exceeded`. Cancellation propagates
and releases queue entries, active permits and response streams. Neither expiry
nor cancellation proves that a submitted backend job stopped. Existing error
recovery guidance and exact submission keys remain authoritative; mutations are
not automatically retried. Callers should reconcile uncertain writes before
repeating them.

The deadline is cooperative: Python parsing, synchronous work and event-loop
scheduling may overshoot the wall-clock target. Reverse proxies and host tool
timeouts must allow sufficient time for the configured operation budget plus
scheduling and error delivery, or they may interrupt it first. No proxy timeout
is changed by this configuration.

A synthetic 24-request burst with six credential identities, mixed small/64 KiB
responses and 15/150 ms backend delays compared uncapped admission with test
values of four active, one active per caller, eight queued, two queued per caller
and a 60 ms total. Baseline completed 24/24, peaked at 24 backend requests and had
165 ms p95 latency. The bounded case completed 5/24, refused 12 as overload and
expired seven; peak backend requests were four and p95 was 65 ms. Python traced
peak allocations were approximately 832 KiB versus 296 KiB. This demonstrates a
resource/latency bound with reduced completion under intentionally tight limits,
not a quality or throughput improvement. It is one mock-transport burst, not
production sizing evidence or a universal memory bound.

A separate exposed development comparison retained all 24 tasks, with a one-second
budget, four active operations, one active per caller and enough queue capacity
for the burst. Both baseline and bounded modes completed 24/24 without overload
or deadline failures. Peak backend requests fell from 24 to four, while p95
latency increased from 164 ms to 326 ms and maximum latency from 164 ms to 405 ms.
Python traced peaks were 854,776 and 820,771 bytes. This workload has no simulated
backend contention penalty, so queueing trades latency for lower concurrency;
it does not demonstrate a latency or cost improvement. The earlier aggressive
comparison is retained as a distinct pre-fairness-fix development result rather
than overwritten. Neither development run is final acceptance evidence.
