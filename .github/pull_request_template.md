## What does this PR do?

<!-- A brief description of the change. -->

## Why?

<!-- Why is this change needed? Link to an issue if applicable. -->

## Architecture and shared code

<!-- Read docs/engineering.md before implementation. For epic #38, reference its
standing engineering objective. State "no structural change" when applicable. -->

- Owning package and responsibility:
- Existing code reused or extracted; reason for new files:
- Dependency direction and compatibility checks:
- Duplicate/stale paths removed, or explicitly tracked structural debt:

- [ ] Reviewed the [engineering objective](https://github.com/getsimba-ai/simba-mcp/issues/38#engineering-objective-coherent-structure-and-shared-code)

## Verification

For tool changes, record the role decision in packaged coverage.json, update canonical
guidance and executable examples, then regenerate counts/Skills/references. Confirm
backend capability and permission boundaries. Explain intentional exclusions and
example limitations rather than automatically expanding every profile.

- [ ] `pytest -v` passes
- [ ] `ruff check src/ tests/` passes
- [ ] `ruff format --check src/ tests/` passes
- [ ] `python -m simba_mcp.guidance.coverage --check` passes

## Notes

<!-- Anything reviewers should know — breaking changes, migration steps, etc. -->
