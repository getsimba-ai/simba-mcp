# Optional tool profiles

Choose a starting view for the job. `full` is the default. `data_scientist` is an
alias for full, including the entire Studies lifecycle and any future tools.
Startup profiles select tools at server construction; hosted account preferences
can narrow that view per caller. Neither grants backend permissions.

<!-- current-role-coverage:start -->

| Profile | Current tools | Intended work |
| --- | ---: | --- |
| `full` | 95 | Mixed jobs and explicit fallback |
| `data_scientist` | 95 | All data, modelling, Studies, review and planning work |
| `marketer` | 55 | Actual-data/campaign reporting, saved evidence, comparisons, authorised plans and run curation |
| `reviewer` | 51 | Scientific evidence/provenance, assessments, declarations and evidence-bound recommendations |

<!-- current-role-coverage:end -->

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

## Hosted connections: the account's profile

With a supporting Simba backend, save Full, Data scientist, Marketer or Reviewer
under Profile > Connected apps. This preference applies to every hosted connection
authenticating as that account, including API keys and OAuth tokens. The MCP server
reads `GET /api/v1/mcp/preferences` with that request's bearer credential. The
endpoint's version-1 contract includes `schema_version: 1` and a valid `profile`.

The account profile narrows the operator's startup catalogue. Choosing Full does
not restore tools omitted by the operator and does not add any backend permission.
An excluded tool call returns `profile_excluded` with instructions to change the
choice. Registered definitions and other callers' catalogues remain unchanged.

Successful preferences are cached for 30 seconds per bearer hash and backend
identity, with at most 1,024 retained entries per process. Tokens are not stored in
the cache or logged. Expired entries are removed on subsequent reads/insertion.
After saving, wait up to a minute, then reconnect the assistant to refresh its tool
list. Reconnection alone does not invalidate the server cache. Existing clients
may retain their discovered tools until they reconnect.

A preference lookup has a five-second overall deadline and is not retried.
Timeout, unavailable/older backend (including 404/503), or an invalid preference
contract retains the operator's catalogue; warnings are limited to one per minute
per process. Authentication failures still reach the existing credential refusal
when a tool uses the backend. Requests without a bearer retain existing key-less
discovery and authentication guidance. Failures are not cached.

This package provides the consumer. The preferences endpoint and Connected apps
control require the corresponding backend rollout. Hosted wire tests use synthetic
backend responses; live deployment and named-client acceptance are separate gates.
Local stdio makes no account preference lookup and retains its launch controls.

## Full fallback and rollback

For a task needing omitted tools, configure a new full connection or restart the
current server with `--profile full`. Environment-only deployments can unset
`SIMBA_TOOL_PROFILE` or set it to `full`. Keep the user's backend permissions and
credentials appropriate to the task. Reconcile any uncertain write before retrying
after a switch; reconnecting does not cancel or undo a backend operation.

There is no tool that changes the server's profile during a conversation. A tool
omitted by the startup profile is not registered; a tool excluded by the hosted
account profile is refused before dispatch. For local connections, several views
require separate server instances, with a full connection available for mixed jobs.
Do not expose duplicate views to the same conversation by default.

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
identical definitions. The 81/37/38-tool comparison is historical evidence for its frozen
29 September catalogue; it does not validate current expanded profiles.

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

## Current role coverage and examples

The [complete tool decision matrix](role-coverage.md) records every tool, its role
membership, guidance and example decision. Marketer and reviewer can find existing
stored datasets with list_uploads/get_upload and report actual KPI/spend with
get_data_schema/get_data_report. Pipeline outputs already appear as uploads, so
pipeline inspection/execution, upload and schedules remain full-only. Required
backend scopes still apply independently of role visibility.

Use [workflow guidance](workflow-guidance.md) for canonical independently installable
Skills and executable synthetic examples. Current role regression evidence covers
exact backend requests and recovery, including no automatic replay of uncertain
mapping writes. It does not establish model-assisted competence or native-client
rendering. See [candidate acceptance](role-candidate-acceptance.md) for exact status.

Counts, this decision matrix and example calls are maintained by
`python -m simba_mcp.guidance.coverage`; use `--check` in CI. Change coverage.json
only after making an explicit role and workflow decision, not to conceal a missing
dependency. Registration and profiles.py remain the runtime source of truth.
