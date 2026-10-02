# Repository engineering guidance

Before picking up an issue or PR, read [the engineering objective](docs/engineering.md).
Reference it in the execution plan and PR architecture note. Identify package
ownership, reuse and dependency direction before adding files. Keep contracts,
execution, fixtures, presentation and CLI responsibilities separate. Prefer focused
shared implementations; avoid duplicate runners and generic helper collections.

For performance epic #38, apply this as an acceptance gate on every child issue.
Use the PR template's architecture section even when the answer is no structural
change. Preserve released contracts and verify behaviour after moving code.

Use British English and no em dash in new prose. Public changes must contain only
publishable code, public contracts and synthetic evidence. Keep local plans and
scratch outputs out of commits and public artifacts.
