# Engineering objective: coherent structure and shared code

This is a standing acceptance requirement for the [performance epic #38](https://github.com/getsimba-ai/simba-mcp/issues/38)
and every child issue and implementation PR.

## When picking up an issue

1. Read this objective and the issue's current evidence before editing.
2. Record the owning package, intended files and dependency direction in the work
   plan. Inspect existing implementations before adding another helper or runner.
3. Reuse a canonical implementation where responsibilities match. Introduce shared
   code only for actual shared behaviour with a clear owner, not speculative reuse.
4. Keep public changes self-contained and grounded in public contracts and synthetic
   fixtures. Publish only material suitable for the public repository.

## Structural rules

- Group related features into cohesive packages as responsibilities grow. Separate
  contracts, execution, fixtures, presentation and CLI entry points.
- Dependencies point towards contracts and focused common primitives. Contracts
  and report renderers must not import execution, CLI or benchmark orchestration.
- Commands may reuse common primitives; one command must not import another command
  merely to obtain a helper. Shared names describe their responsibility, such as
  `measurements`, rather than becoming an unbounded `utils` module.
- Keep tool/business ownership in the existing domain modules. Do not put scientific
  policy, backend state or another application's orchestration into MCP helpers.
- Keep tests aligned with feature ownership. Use targeted architectural regression
  tests when a dependency boundary is important enough to protect.
- Move the canonical implementation and update consumers together. Remove abandoned
  paths. Preserve released interfaces deliberately; document compatibility shims and
  their lifetime if needed. Do not leave duplicate implementations behind.
- Never make a folder-only abstraction: every new package or shared helper needs an
  actual responsibility and consumer. Record a justified no-change decision for
  tasks that do not affect structure.

## Evaluation ownership

```text
src/simba_mcp/
  measurements.py         # shared summaries, serialisation and provenance
  performance.py          # catalogue measurement command
  benchmark.py            # instrumentation overhead command
  telemetry.py            # runtime observations
  evaluation/
    __init__.py            # contract exports
    __main__.py            # command-line interface
    contracts.py           # scenario and report data models
    runner.py              # deterministic execution
    cases.py               # public synthetic scenarios
    reporting.py           # report presentation
tests/
  evaluation/              # contract, runner and package-boundary tests
```

`evaluation.runner` and `benchmark` reuse `measurements`; neither imports the other.
`evaluation.contracts` depends on data-validation primitives only. `evaluation.reporting`
accepts report data and does not execute tools. This describes module ownership;
it does not change the existing top-level package initialisation contract.

## Every PR and issue handover

Reference this objective and state:

- which package owns the change and why;
- what existing code was reused or extracted, and why new files are necessary;
- which dependency boundaries and compatibility contracts were checked;
- how stale paths, duplicate implementations and generated scratch files were avoided;
- the verification performed and any explicitly tracked structural debt.

Reviewers should reject unexplained duplication, circular dependencies, misplaced
responsibilities and avoidable folder sprawl. Apply this gate before merge, alongside
behavioural tests. A performance improvement does not waive maintainability.

## Secret protection

GitHub secret scanning and repository push protection provide native detection for
supported credential formats. The required `Gitleaks` CI check also scans all commits
introduced by each pull request. Main-branch pushes and manual runs scan the available
history. The workflow pins Gitleaks 8.30.1 and verifies the release archive's SHA256.
Scanner output is redacted; do not publish unredacted findings.

Before pushing, run the same scanner locally:

```bash
gitleaks git . --config .gitleaks.toml --redact --no-banner --log-opts="--all"
```

`.gitleaks.toml` retains the upstream rules and adds detection for Simba API keys
and OAuth tokens with suffixes of at least 32 characters. Its exceptions apply only
to an exact short dummy key in one verifier test and source-file digest lines in
two historical synthetic evidence files. Keep exceptions narrow and justified;
never exclude an entire test or documentation directory. If a real credential is
found, revoke or rotate it, then remove it from the source. Deleting a committed
credential does not undo its exposure.
