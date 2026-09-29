# Measuring MCP performance

The commands below inspect the local installed server and use synthetic data.
They do not call the Simba backend, fit a model or call a model provider.
The [design and evaluation handover](performance-design.md) defines the boundaries.

## Tool definitions

From a source checkout with development dependencies installed:

```bash
python -m simba_mcp.performance --output-dir .codex/performance
```

This starts the real HTTP app in memory, captures `initialize` and `tools/list`,
and writes `surface.json` and `surface.md`. It records the exact local HTTP JSON
response body, public tool fields and instructions, registration order, package
versions, source digest, Git revision and dirty state. Byte counts exclude HTTP
headers and compression. Results from an installed wheel can have a null Git
revision; the Python source digest still identifies the measured code.

Token estimates are optional:

```bash
pip install -e ".[dev,performance]"
python -m simba_mcp.performance --encoding o200k_base --output-dir .codex/performance
```

The tokenizer may download its public encoding asset on first use. Cache that
asset before running without network access. Record the named encoding and package
version when comparing reports. This encoding is a comparison convention, not an
assertion about the model used by your host. Field token counts encode each field
independently and cannot be summed to obtain catalogue tokens.

Actual model input, cached-input and output usage remain unavailable until captured
from a host trial. A large catalogue does not establish how much a host sends to
its model or whether deferred discovery improves a particular task.

## Optional request observations

Metrics are disabled by default. To emit one numeric JSON event per tool call to
stderr, set `SIMBA_MCP_METRICS=stderr` in the server's environment. Unset it to disable.
No metrics are written to stdio's protocol stream. Other values leave metrics off.

The event contains a fixed tool name, outcome, elapsed time, backend attempt count,
allowlisted route templates/status classes, downloaded and decoded body byte counts,
parsing/filtering/byte-cap serialisation time and serialised tool-result sizes.
At most 32 attempt details are retained per invocation; `dropped_attempt_details`
makes truncation explicit. Unknown tools or routes use `other`.

Backend attempt duration includes body download, but excludes retry backoff and
subsequent JSON parsing. Total tool duration includes validation, retries and SDK
conversion. It excludes the additional metric result serialisation and sink work.
`measurement_serialisation_seconds` describes this additional serialisation only.
`content_json_bytes` counts the content array; `call_tool_result_json_bytes` counts
the whole result including structured/text duplication. Neither includes the
JSON-RPC envelope, transport framing or compression. Those transport bytes and
provider usage are explicitly null in request observations.

The sink never receives credentials, URLs, query values, arguments, raw bodies,
error messages or caller/model/study identifiers. Counting a result requires an
extra in-memory serialisation when enabled. No result text is retained by the
collector. A missing byte count means unavailable, not zero. For example, HTTPX
prebuffered mock responses may not have a downloaded-byte measurement.

An embedding application can use `telemetry.use_sink(callable)` as a context manager
to receive events in that task and its children. `use_sink(None)` forces metrics
off in that context. The callback is synchronous trusted application code; keep it
prompt and non-blocking. Sink exceptions do not fail normal tool calls. A slow
stderr consumer can add latency, so use this diagnostic option deliberately.
Built-in SDK OpenTelemetry is configured separately and is unaffected.

## Synthetic overhead baseline

```bash
python -m simba_mcp.benchmark --samples 30 --output-dir .codex/performance
```

This exercises real SDK tool conversion against HTTPX MockTransport for a small
status response, a larger results response and filtered results. It checks identical
results with measurements disabled, collected in memory and written as stderr JSON
to a buffered temporary file. It writes `overhead.json` and `overhead.md` with the
fixture version/digest, provenance, first-iteration timings, warm sample counts,
median/p95 and differences from disabled measurements.

Modes are interleaved, with alternate rounds reversed to reduce order bias.
"First iteration" is per case/mode in a shared process, not a cold network or
fresh operating-system cache. Fixtures and the mock client are prepared outside
the timer. Warm samples reuse them. These timings include the metric sink and
additional result serialisation, unlike the event's tool-duration measurement.
No arbitrary overhead threshold is enforced by CI.

The benchmark measures instrumentation overhead only. It is not evidence of faster
production workflows. PERF-02 adds task correctness, host usage, repeated model
trials and reviewed budgets before subsequent optimisations change defaults.

## CI evidence

CI runs the current SDK on Python 3.11, 3.12 and 3.13, plus the supported MCP 2.1.0
floor on Python 3.11. Both Python 3.11 configurations produce the surface and
synthetic overhead reports as workflow artifacts, named `performance-current`
and `performance-2.1.0`, retained for 90 days. These artifacts identify their
checked-out revision and fixture digest. They are measurement records, not
performance pass/fail thresholds. Preserve any release evidence beyond artifact
expiry as part of PERF-02.
