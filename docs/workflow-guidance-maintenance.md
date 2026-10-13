# Maintaining workflow guidance

This page is for contributors changing Simba's packaged AI instructions. For what
the instructions are and how to use them, start with
[AI workflow instructions for Simba](workflow-guidance.md).

## Source ownership

`src/simba_mcp/guidance/content/` is the canonical source, included in the wheel and
source distribution. Its manifest owns the guidance version, stable topic and section
IDs, and the source file for each section. The reader resolves only manifest entries.

`src/simba_mcp/tools/guidance.py` exposes the reader through MCP. The export CLI
generates standalone `skills/` folders from the same content. Runtime lookup never
imports the export CLI, evaluator, or runner. Prior details have one canonical owner
and are copied into generated standalone distributions.

This follows the [engineering objective](engineering.md). Edit canonical content,
not generated native copies. CI checks that generated Skills match their source.

## Change and verify instructions

Update the manifest version when the meaning of the guidance changes. Editorial
changes to user documentation alone do not change the packaged instructions.

From the repository's Python development environment, run:

```shell
python -m simba_mcp.reference
python -m simba_mcp.guidance.coverage
python -m simba_mcp.guidance
python -m simba_mcp.guidance --check
python -m simba_mcp.guidance.coverage --check
pytest tests/guidance tests/evaluation
```

Generate references before exporting Skills. Version 22 includes full `tool-reference`
sections for `mmm`, `results`, and `optimiser`, generated from existing handler
docstrings. See [compact descriptions](compact-descriptions.md) for the optional
compact tool catalog mode and rollback instructions.

Preserve request recovery, exact identifiers, units, missing-evidence semantics, and
human authority. Each structured response must remain within the 24,000-byte UTF-8
limit; MCP transport adds overhead. Oversized sections must be refused without
partial instructions, and unknown IDs must retain a recovery action.

## Compatibility

The four original Skill names remain available. `simba-mmm-workflow` focuses on
building; results and Studies have separate starting instructions. Version 22 adds
`simba-campaign-workflow` and `simba-data-reporting`, with all six earlier workflows
reconciled against current role boundaries and prerequisites. Existing Skill names
and section IDs remain valid.

The guidance tool is additive. Existing tool handlers, parameters, and detailed
descriptions remain unchanged. Adding guidance increases tool catalog size; lower
end-to-end token use or latency needs measured model trials.

## Executable example coverage

The [role decision matrix](role-coverage.md) covers the complete current catalog.
Examples are generated from the public Case/Step/Exchange contracts used by the
existing strict runner, through selected profiles and mocked backend exchanges.

| Task | Topic / detail | Example section | Boundary |
| --- | --- | --- | --- |
| Actual KPI/spend, dataset discovery, oversized-result recovery | reporting / workflow | workflow-examples | All profiles; no upload or refresh |
| Campaign facts and incremental attribution | campaigns / workflow | workflow-examples | All profiles; retain platform versus incremental meaning |
| Complete mapping replacement and uncertain-write recovery | campaigns / mapping | mapping-examples | Marketer/full with explicit intent; reviewer stops |
| Marginal evidence and conditional daily budgets | campaigns / budgets | budgets-examples | All profiles; read-only calculation, no platform changes |
| Experiment priorities and unsupported-backend recovery | campaigns / experiments | experiments-examples | All profiles; screening only |
| Response curves/decomposition and JSON-only clients | results / visuals | visuals-examples | All profiles; no prediction access or fit |
| Compare exact saved optimizer runs | optimiser / saved | saved-examples | All profiles; no new planning run |
| Missing Studies evidence | studies / review | review-examples | All profiles; missing diagnostics never pass |
| Authorized model build prerequisites/full fallback | mmm / building | building-examples | Full/data_scientist; synthetic fixture starts no real fit |

Each example section stays within the response limit. Deterministic checks establish
packaging, schemas, requests, and evidence preservation. They do not establish
native-client discovery, model competence, scientific correctness, or measured
token/latency improvements. Live task completion through native clients remains
unverified; other clients' discovery mechanisms need their own checks. Repeated model
evidence and approved budgets remain separate PERF-02 acceptance gates. See
[candidate acceptance](role-candidate-acceptance.md) for checks and rollout limits.

## Upgrade and rollback

Users must re-export and reinstall complete Skill folders after upgrades. Reconnecting
MCP does not refresh installed copies. To roll back, restore a previously exported
complete Skill set and the prior package, then restart the server, reconnect, and
verify `tools/list`.

Use `--profile full` for explicit cross-role recovery where appropriate; it does not
change caller permissions. Already-loaded guidance need not be fetched again. For
known tasks, request the topic and section directly rather than repeating discovery.
