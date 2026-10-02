# Workflow guidance

Guidance version 2 separates model building, existing results, priors, optimisation,
Studies and VAR. Each entrypoint states its trigger, checks and recovery path, with
detailed references loaded only when relevant. Guidance is not authorisation and
does not replace backend validation or human acceptance.

## Install native Skills

Install the MCP server separately using the README instructions. From an environment
with this package installed, export the native folders to a chosen staging directory:

```shell
python -m simba_mcp.guidance --output-dir exported-skills
```

Copy each desired complete folder, including `references/`, into the client's Skill
location. Do not copy just `SKILL.md`. Each folder is independently installable;
shared prior details are included during export. Review existing installations before
replacing them. Exporting or connecting MCP does not automatically enable a Skill.

| Client route | Installation and discovery | Verification boundary |
| --- | --- | --- |
| Claude Code native Skills | Copy folders into `.claude/skills/` in the project or `~/.claude/skills/`; invoke `/simba-results-analysis`, for example | Documented client mechanism; generated folders and links tested. Live model task completion remains unverified |
| Other Agent Skills clients | Install complete folders using the client's documented Skill mechanism | Portable standard format; client-specific discovery remains untested |
| MCP clients without native Skills | No Skill installation; call `get_workflow_guidance` when relevant guidance is needed | Dispatch, content parity and bounded errors tested; model selection and task quality remain unverified |

Sources checked 29 September 2026: [Agent Skills specification](https://agentskills.io/specification)
and [Claude Code Skills documentation](https://code.claude.com/docs/en/skills).

## Bounded MCP fallback

```json
{"topic": "index"}
```

This lists topic IDs, descriptions and allowed sections. If the topic is already known,
request it directly, without an index round trip:

```json
{"topic": "results", "section": "entrypoint"}
```

Read the referenced detail only when required, for example:

```json
{"topic": "results", "section": "interpretation"}
```

Other topics are `mmm`, `priors`, `optimiser`, `studies` and `var`. The response carries
`guidance_version`, available section IDs and the exact content SHA-256. A native
relative link such as `references/interpretation.md` maps to section `interpretation`
within the current topic. The fallback performs no network or backend call. It accepts
only allowlisted IDs, never a path or URL. The structured guidance payload is capped at 24,000
UTF-8 bytes (the MCP envelope adds transport overhead); oversized content produces a refusal without partial instructions.
Unknown IDs produce a structured tool error with a recovery action.

Already-loaded guidance need not be requested again. For an existing-result question,
start with the known model and selected result sections; do not require capability or
data-schema calls. New data still requires schema checks, and operation-specific
capability gates remain necessary before unsupported model/configuration/publication work.

## Compatibility and ownership

The four original Skill names remain available. `simba-mmm-workflow` now focuses on
building; results and Studies have explicit entrypoints. Install those additional
folders or use the fallback when those tasks arise. Existing tool handlers, parameters
and detailed descriptions remain unchanged. The local guidance tool is additive; it
adds catalogue bytes, so lower end-to-end usage is a hypothesis pending model trials.

`src/simba_mcp/guidance/content/` is the canonical source included in the wheel and
source distribution. Its manifest owns stable topic/section IDs and version. The
reader resolves only manifest entries. `tools/guidance.py` adapts it to MCP; the export
CLI generates `skills/` from the same content. Runtime lookup never imports the export
CLI, evaluator or runner. Prior details have one canonical owner and are copied only
into generated standalone distributions. This follows the
[epic engineering objective](engineering.md).

Edit canonical content, update its version when guidance semantics change, then run:

```shell
python -m simba_mcp.reference
python -m simba_mcp.guidance
python -m simba_mcp.guidance --check
pytest tests/guidance tests/evaluation
```

Do not edit generated native copies directly. CI verifies parity. Preserve request
recovery, exact identifiers, units, missing-evidence semantics and human authority.
Deterministic checks establish packaging and contracts, not native-client competence,
scientific correctness or a measured token/latency improvement. Repeated model evidence
and approved budgets remain separate acceptance gates in PERF-02.

Version 2 includes generated full `tool-reference` sections for `mmm`, `results`
and `optimiser`. Their source is the existing handler docstrings. Generate references
before exporting Skills. See [compact descriptions](compact-descriptions.md) for
the opt-in catalogue mode and rollback instructions.
