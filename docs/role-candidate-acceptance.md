# Role guidance candidate acceptance

Checked 2 October 2026. This records the candidate for [epic #91](https://github.com/getsimba-ai/simba-mcp/issues/91),
not package publication or hosted deployment. Source base is `d2df6e1`; the implementation
PR and its current-head CI identify the exact candidate. Python 3.12.13 on Windows,
MCP SDK 2.2.0, package candidate 0.16.0 and shared guidance 22 were inspected locally.
The [generated counts and decisions](tool-profiles.md) are authoritative for this source.

## Evidence and acceptance boundary

| Check | Status | Evidence and limit |
| --- | --- | --- |
| Current complete role workflows and recovery | PASS | 52 registered profile/case executions, strict synthetic requests, zero unintended writes |
| Targeted guidance/profile/workflow regression | PASS | 122 checks, including negative drift fixtures and real SDK transports |
| Full local suite | PASS | 1,014 passed, one browser module skipped because Playwright was absent, three existing SDK OAuth deprecation warnings |
| Packaged native-view iframe regression | PASS | Installed Playwright/Chromium and ran the skipped browser module separately: three passed; this is still separate from named-host acceptance |
| Lint and format | PASS | Ruff check and format across src/tests |
| Generated reference, configuration, coverage/counts/examples and native Skills | PASS | Existing generation/check commands, no stale outputs |
| Isolated built-wheel guidance/export and current marketer job | PASS | Eight topics, bounded content, complete independently exported folders and registered synthetic reporting |
| Installed-wheel operator configuration | PASS | Existing isolated installation check, valid/invalid settings without secret output |
| Clean environment/package install | PASS | Fresh Python 3.12 environment; wheel install and guidance/current reporting smoke |
| Stdio/HTTP profile selection, invalid startup, explicit full fallback | PASS | Existing SDK/wire tests, unchanged credentials and released tool schemas |
| Independent server instances/callers | PASS | Existing mixed-transport and parallel caller-context tests |
| MCP fallback content parity and errors | PASS | Actual registered dispatch; allowlisted IDs, unknown/oversize refusal and matching export content |
| Named client native-Skill discovery/model completion | NOT RUN | MCP/client maintainer owns intended-host acceptance; packaged/export checks do not prove client competence |
| Named native-chart host rendering | NOT RUN | Feature-specific acceptance remains with #83; JSON fallback is tested |
| Current model-assisted role performance | NOT RUN | Evaluation maintainer under #40 must specify method, acceptance and approved budget; historical reports remain frozen |
| Hosted profile selector/configuration | NOT RUN | Configuration owner under #70; no untested application selector is claimed |
| Package publication, endpoint upgrade and live workflows | NOT RUN | Release/operator ownership under #50/#51; source and wheel candidate are distinct from deployment |

No latency, cost, scientific-validity or live production improvement is claimed.
Unavailable checks stay unavailable. A maintainer must record the supported release
scope before #97 or the epic closes. This document does not make that decision.

## Reproduce the candidate checks

Use a clean checkout of the implementation PR with Python 3.11 to 3.13, then install
`.[dev,performance]`. Keep real credentials unset for synthetic verification.

```shell
pytest -v
ruff check src/ tests/
ruff format --check src/ tests/
python -m simba_mcp.reference --check
python -m simba_mcp.configuration --check
python -m simba_mcp.guidance.coverage --check
python -m simba_mcp.guidance --check
python -m simba_mcp.evaluation --roles --description-mode compact --output-dir .codex/evaluation/roles
python -m pip wheel . --no-deps --wheel-dir .codex/wheel
python -I tests/guidance/wheel_smoke.py .codex/wheel
python -I tests/configuration_wheel_smoke.py .codex/wheel
```

The role report records package/SDK/Python versions, commit and dirty flag, source,
catalogue and fixture digests, guidance version and per-profile assertions. CI stores
this report with the current-head workflow artefacts. Historical provider JSON and
frozen paid role task assignments are not rewritten. Source-changing acceptance is
not inferred from an old report or the baseline commit alone.

## Upgrade, reconnect and rollback

1. Before upgrading, retain the currently working package version, server startup
   configuration and complete native Skill folders. Publication is a separate operation.
2. Install the chosen published package or an explicitly identified wheel candidate.
   Preserve API URL, credentials and caller permissions. Set the server's exact
   `--profile marketer`, `reviewer`, `data_scientist` or `full` startup value.
3. Restart the server and reconnect the client. Inspect tools/list to confirm the
   effective catalogue; a client-side title or cached catalogue is not proof of selection.
   Separate hosted instances/connections are needed for different startup profiles.
4. Export guidance from that package into a staging folder. Replace/install each
   desired COMPLETE Skill folder, including references, using the client's supported
   mechanism. Connecting MCP alone neither installs nor updates Skills.
5. For a known task, call its guidance topic/section directly. Inspect guidance_version
   and use a harmless existing-result read before any user-authorised write. Keep
   campaign facts, model attribution and actual dataset reports distinct.
6. Roll back by reinstalling the retained package and complete Skill set, restarting
   and reconnecting, then confirming tools/list. For a cross-role task, explicitly
   configure full. Reconcile uncertain writes against authoritative backend state
   before any retry; a reconnect does not cancel, undo or authorise replay.

## Engineering ownership

Follow [docs/engineering.md](engineering.md). profiles.py owns membership and server
registration owns exposure. Canonical guidance owns content; existing evaluation
contracts/runner own fixtures and execution. The focused coverage command owns
maintenance validation and generated presentation. Runtime guidance does not import
that command or evaluation code. There is no copied runner, runtime selector or
independently maintained schema registry. Existing public contracts remain unchanged.
