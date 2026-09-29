# Initial measurement baseline

Captured 29 September 2026 for [PERF-01](https://github.com/getsimba-ai/simba-mcp/issues/39)
in [PR #52](https://github.com/getsimba-ai/simba-mcp/pull/52).

## Provenance and verification

- Implementation head: `29f3043e7f84cebc6cd6e73bed3cc12cd73b4e7e`.
- CI tested merge revision: `5f680f8c9bed5b1461f06e6f81cbbc3d96aa0638`, clean checkout.
- Python-source SHA-256: `5b97320a568badaa2a9a79b9fc68951a13b0e4c7b44be4c2a2c6a1c8767b3022`.
- Synthetic fixture version 1, SHA-256: `11f50f5b35d196af47889dc22ba90eec3516655c049e93f5ab688498fac14240`.
- Report environment: Linux x86_64, Python 3.11.16, HTTPX 0.28.1, Pydantic 2.13.5, tiktoken 0.14.0. SDK configurations: MCP 2.1.0 and 2.2.0.
- [CI run](https://github.com/getsimba-ai/simba-mcp/actions/runs/36517970679): all four jobs passed, covering Python 3.11/3.12/3.13 with current MCP and Python 3.11 with the MCP 2.1.0 floor.
- [Current SDK reports](https://github.com/getsimba-ai/simba-mcp/actions/runs/36517970679/artifacts/11011886470) and [SDK-floor reports](https://github.com/getsimba-ai/simba-mcp/actions/runs/36517970679/artifacts/11011946334) include JSON and Markdown surface/overhead records. GitHub artifact access requires sign-in and retention is 90 days. The summary and digests here remain versioned in the repository.

## Catalogue

Both SDK versions produced the same 80-tool HTTP catalogue body:

| Representation | UTF-8 bytes | o200k_base token estimate |
| --- | ---: | ---: |
| tools/list HTTP JSON-RPC response body | 164575 | 36956 |
| Server instructions encoded as a JSON string | 910 | 163 |

Catalogue SHA-256: `a458dd990ab56863c59c1c9e24540b96b4f3d912f61fde46ce980cebe2a009e5`.
These numbers describe local protocol representations. Actual host/model usage is
unavailable. They do not establish how many definitions a host sends to its model.

## Instrumentation overhead

Median milliseconds from 30 warm samples per configuration on MCP 2.2.0:

| Synthetic case | Metrics disabled | In-memory collection |
| --- | ---: | ---: |
| Small status response | 0.150 | 0.171 |
| Large results response | 5.740 | 9.606 |
| Filtered results with output byte cap | 9.700 | 13.252 |

All modes returned identical results. The complete artifacts also contain first
iterations, p95, stderr sink results and MCP 2.1.0 results. Modes alternate order
and share fixtures/client state; first iterations are not cold network measurements.
No real backend, model-provider call or production fit was involved.

Counting large result representations adds measurable serialisation cost. Metrics
therefore remain disabled by default. These measurements establish neither a
production performance improvement nor an approved overhead budget. PERF-02 must
measure correctly completed workflows and actual host usage before optimisations
are judged or defaults change.
