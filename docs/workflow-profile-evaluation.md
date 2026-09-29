# Fixed workflow profiles: evaluation and proposed deferral

Decision proposed for issue #44: defer production profiles. Owner approval is
pending. Keep the full compact catalogue available and native discovery experimental.
This is a conditional optimisation, not a required new server feature.

## Offline evidence

On merged revision `4f64166`, capture the real compact HTTP `tools/list`, filter its
tool objects without changing schemas or order, and measure the same JSON result
representation with `o200k_base`. The [evidence manifest](workflow-profile-evidence.json)
records exact candidate membership, hashes and fixture-name coverage. No provider
calls, live backends or real fits were used. Estimates are not billed model tokens.

| Candidate | Tools | JSON bytes | Estimated tokens | Combined results/study tool availability |
| --- | ---: | ---: | ---: | --- |
| Full compact | 81 | 140,593 | 31,716 | Complete |
| Analysis | 8 | 10,652 | 2,381 | Missing study evaluation lookup |
| Model building | 33 | 56,790 | 13,225 | Missing study evaluation lookup |
| Optimisation | 16 | 28,506 | 6,569 | Missing study evaluation lookup |
| Study authoring | 62 | 100,597 | 22,380 | Available |
| Study review | 27 | 32,967 | 7,239 | Available |

Candidates include common guidance, capabilities, model lookup/status/results and
project lookup. Broader candidates add existing domain groups to account for
prerequisites and recovery, rather than enforcing a numeric tool limit. Membership
is an evaluation hypothesis, not a supported configuration or proof of completeness.
Available fixture tool names do not establish correct model selection, usable
recovery, caller isolation or end-to-end success. These sets are not registered or shipped.

## Why defer

Smaller catalogues clearly offer potential size savings. However, no specific eager
client has yet been demonstrated to need fixed profiles, and no paired profile task
trial establishes an improvement. The existing eager/deferred comparison tests a
different mechanism and cannot answer that question.

Three narrow candidates omit a required operation in the existing mixed-domain
fixture. Widening the authoring candidate already restores 62 of 81 tools. This
illustrates the tradeoff: each profile needs deliberate prerequisite/recovery
maintenance, and mixed workflows need an explicit full endpoint. It does not prove
that all possible profiles fail or that larger candidates are complete.

The previous provider trials also showed answer-format and evidence-interpretation
weaknesses. Reducing tool count has not been shown to fix them. Prioritise the
required selective-results work in #45 while preserving the working full catalogue.

## Revisit condition and implementation gates

Reopen this decision when a named, versioned eager client has a reproducible context,
latency or routing problem that compact descriptions cannot address. Require a
bounded paired trial, with approved spend and targets, showing reduced total cost or
latency without additional failures, missing recovery operations or unintended writes.
Include the mixed-domain fixture and an explicit full-catalogue fallback.

If that evidence justifies implementation, use the existing server factory with
fixed startup configuration. Verify invalid configuration, separate instances,
credentials/runtime isolation, stdio/HTTP/import compatibility and unchanged full
endpoint behaviour. Do not introduce runtime enable-tools actions or microservices
per workflow. Those conditional implementation checks are not claimed completed by
this offline evaluation.

## Structure and acceptance

This decision follows the [engineering objective](engineering.md). It adds only a
decision record and an evidence manifest; production packages and configuration
remain unchanged. Measurement reuses `performance.capture_surface`,
`measurements.compact`, canonical cases and the existing mixed-domain host fixture.
No second runner, tool registry, schema collection or profile configuration is added.

Issue #44 explicitly requires owner approval of implement/defer. Keep it open until
that approval is recorded. A maintainer-approved deferral with this fallback and
revisit condition satisfies its conditional decision gate; it is not a claim that
profile behaviour was implemented or tested in a client.
