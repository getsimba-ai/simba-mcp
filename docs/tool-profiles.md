# Optional tool profiles

Choose a starting view for the job. `full` is the default. `data_scientist` is an
alias for full, including the entire Studies lifecycle and any future tools.
Profiles select tools at server startup; they never grant backend permissions.

| Profile | Current tools | Intended work |
| --- | ---: | --- |
| `full` | 81 | Mixed jobs and explicit fallback |
| `data_scientist` | 81 | All data, modelling, Studies, review and planning work |
| `marketer` | 37 | Reporting, model/Studies evidence, comparisons, scenarios, optimisation, saved-run curation and incrementality records |
| `reviewer` | 38 | Scientific evidence/provenance review, assessments, validation pairs, holdout-use declarations and evidence-bound recommendations |

A marketer who also builds models should choose full. A reviewer who authors
recipes or changes quality-policy rules should choose full. The reviewer view can
write assessments, declarations and recommendations; it is not read-only. Some
evidence operations append access audit events. Recommendations do not accept or
promote a model, and a title does not confer analyst sign-off rights.

## Configure a connection

The same setting works for stdio, HTTP and SSE. Existing authentication setup is
unchanged. For a local stdio connection:

```shell
simba-mcp --profile marketer
```

Alternatively, set `SIMBA_TOOL_PROFILE=marketer` in the server process environment.
For a client's existing local configuration, add the arguments:

```json
{
  "command": "simba-mcp",
  "args": ["--profile", "marketer"],
  "env": {"SIMBA_TOOL_DESCRIPTIONS": "compact"}
}
```

This is the connection entry, not a complete client-specific configuration file.
Keep the existing API URL and credential configuration. Description mode is
independent: legacy remains the default, and `compact` is separately opt-in.
The published provider comparison used compact descriptions in both arms.

For an HTTP deployment use the same CLI with `--transport streamable-http`, or
set `SIMBA_TOOL_PROFILE` in the process running `uvicorn simba_mcp.server:app`.
Hosted callers still supply their own bearer credentials. Do not create a shared
identity merely because several users choose the same profile.

The CLI flag overrides a valid environment selection. Invalid environment values
fail during module import, even if a CLI override was supplied. Unknown CLI values
fail before serving. Names are exact and case-sensitive. Restart/reconnect after a
configuration change so the client refreshes its tool catalogue.

## Full fallback and rollback

For a task needing omitted tools, configure a new full connection or restart the
current server with `--profile full`. Environment-only deployments can unset
`SIMBA_TOOL_PROFILE` or set it to `full`. Keep the user's backend permissions and
credentials appropriate to the task. Reconcile any uncertain write before retrying
after a switch; reconnecting does not cancel or undo a backend operation.

There is no tool that changes the server's profile during a conversation. An omitted
tool is not registered and cannot be called by guessing its name. To offer several
views, configure separate server instances/connections, with a full connection
available for mixed jobs. Do not expose every view to the same conversation by
default, which would duplicate definitions and undermine the saving.

## Embedded use and isolation

```python
from simba_mcp.server import create_server
from simba_mcp.runtime import create_app

marketing = create_server("compact", profile="marketer")
scientific = create_server("compact", profile="data_scientist")
app = create_app(marketing)
```

Explicit factory calls do not read the profile environment variable. Each instance
registers the selected canonical handlers in their original order, with unchanged
schemas, annotations and error wrappers. The module-level server remains the
environment-configured entry point for existing imports and deployment commands.

Each lifespan captures its transport mode. Network clients have no default backend
credential; each request supplies its own. Stdio retains its configured environment
key. Local-file policy reads the lifespan mode, and caller credential overrides are
restored when dispatch ends. Creating one network instance cannot turn another
instance into a network server. The legacy process-mode helper remains a fallback
for direct integrations that supply old contexts without lifespan mode metadata.

## Evidence and acceptance

The [paired evaluation](workflow-profile-evaluation.md) ran 110 synthetic provider
sessions. These results support the opt-in implementation; they are not production
latency guarantees or scientific MMM validation. Data scientist and full expose
identical definitions; marketer/reviewer definitions match their evaluated subsets.

Automated acceptance includes real SDK stdio sessions, HTTP wire listing/calls,
invalid startup, excluded-tool refusal, full fallback, registered role workflows,
incrementality imports, quality/provenance operations, scenario curation and mixed
transport/caller isolation. Backend exchanges are mocked. Named desktop clients,
live backend workflows and production deployment remain separate rollout checks.

The design uses standard [MCP tools/list and tools/call](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
(checked 29 September 2026), with SDK 2.2.0 inspected locally and the supported SDK
minimum checked in CI. There is no custom discovery protocol. Following the
[engineering objective](engineering.md), `profiles.py` owns membership and selection;
registration and the existing evaluation host share it. Domain handlers and backend
policy remain in their existing owners.
