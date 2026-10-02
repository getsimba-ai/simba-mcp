# Server configuration

Generated from `simba_mcp.configuration`. Do not edit this page by hand.
Check it with `python -m simba_mcp.configuration --check`.
The installed wheel includes this reference. Source checkouts also check docs/configuration.md.

Runtime owns resolution. This page and `python -m simba_mcp.configuration`
report the same controls without becoming a second settings framework or an MCP tool.

## Product decision

This release does not add an application settings UI. Connection credentials
stay in the MCP host configuration. Operator ceilings stay in the server process
environment or launch arguments. Agents choose documented per-call tool arguments
and cannot raise server ceilings, change the shared catalogue or expand permissions.
A UI is not required for this release. Concise-versus-detailed preferences remain
unimplemented proposals, not settings.

A development `.env` configures only the process that loads it. It does not
configure a remote server, a hosted MCP endpoint or every client.

## How to inspect

```bash
python -m simba_mcp.configuration
python -m simba_mcp.configuration --deployment asgi
```

The JSON report omits credential values, URL userinfo, queries and rejected
inputs. Exit code 2 means a control would fail server startup. Warnings do not
change the effective value. This check does not connect to the backend and does
not prove a hosted deployment.

## Precedence

1. Server constants and operator process settings bound every caller.
2. `--profile` overrides `SIMBA_TOOL_PROFILE` for the CLI process only.
3. HTTP/SSE ignores `SIMBA_API_KEY` and uses the request bearer.
4. Per-call arguments can select evidence or impose a tighter content cap.
   They cannot raise byte ceilings, disable admission or enable server filesystem reads.
5. Backend authorisation remains definitive.

## Examples, not measured production defaults

Local stdio: set the backend URL and operator key. Leave description mode, profile,
request policy and byte ceilings at their defaults unless the operator has a measured
reason to change them. The localhost URL is a development default, not a hosted recommendation.

Hosted HTTP: launch `streamable-http` or `uvicorn simba_mcp.server:app`. Callers
authenticate with their own bearer. The operator key is unused. Local files stay
denied unless the operator explicitly enables them. OAuth mode stays off unless
this deployment serves protected-resource metadata. Do not copy a numeric request
policy from this document; none is recommended here.

## Inventory

| Identity | Kind | Owner module | Owner | Scope | State |
| --- | --- | --- | --- | --- | --- |
| `SIMBA_API_URL` | environment | `simba_mcp.runtime` | operator | process | default http://localhost:5005 |
| `SIMBA_API_KEY` | environment | `simba_mcp.runtime` | operator for stdio; authenticated caller for HTTP/SSE | process on stdio; request on HTTP/SSE | absent until set; never a shared fallback on HTTP/SSE |
| `SIMBA_API_REQUEST_POLICY_JSON` | environment | `simba_mcp.request_budget` | operator | process | disabled unless set; JSON false also disables it |
| `SIMBA_API_MAX_ENCODED_BYTES` | environment | `simba_mcp.runtime` | operator | process | unset inherits the decoded ceiling; neither set means no local ceiling |
| `SIMBA_API_MAX_DECODED_BYTES` | environment | `simba_mcp.runtime` | operator | process | unset inherits the encoded ceiling; neither set means no local ceiling |
| `SIMBA_TOOL_DESCRIPTIONS` | environment | `simba_mcp.server` | operator | process catalogue | default legacy; compact is opt-in |
| `SIMBA_TOOL_PROFILE` | environment | `simba_mcp.server` | operator | process catalogue | default full |
| `--profile` | argument | `simba_mcp.__main__` | operator | process | optional; absence leaves the environment or default |
| `--transport` | argument | `simba_mcp.__main__` | operator | process | default stdio |
| `--host` | argument | `simba_mcp.__main__` | operator | process | default 0.0.0.0; unused for stdio |
| `--port` | argument | `simba_mcp.__main__` | operator | process | default 8100; unused for stdio |
| `SIMBA_MCP_ALLOW_LOCAL_FILES` | environment | `simba_mcp.auth` | operator | process | stdio allows by default; HTTP/SSE denies unless explicitly enabled |
| `SIMBA_MCP_METRICS` | environment | `simba_mcp.telemetry` | operator | process, with a task-local override for embeddings and benchmarks | off unless the value is exactly stderr |
| `MCP_OAUTH_ENABLED` | environment | `simba_mcp.oauth` | operator | process | off unless 1, true or yes |
| `SIMBA_PUBLIC_URL` | environment | `simba_mcp.oauth` | operator | process | default http://localhost:8100; unused while OAuth is off |
| `MAX_UPLOAD_BYTES` | constant | `simba_mcp.runtime` | maintainer | build | 10485760 bytes |
| `MAX_REQUEST_BODY_BYTES` | constant | `simba_mcp.runtime` | maintainer | build | 12582912 bytes |
| `DEFAULT_TIMEOUT` | constant | `simba_mcp.api_client` | maintainer | build | 60.0 seconds; up to 3 read attempts |

### `SIMBA_API_URL`

- Purpose: Backend base URL for the shared client.
- Lifecycle: Read at lifespan start. Restart to change. A development .env configures only the process that loads it.
- Resolution: Environment, otherwise the default. Userinfo, query and fragment are credentials, not configuration to display.
- Authority: Operator. Callers cannot change the shared client URL.
- Evidence: Existing local default. No production URL is selected by this inventory.

### `SIMBA_API_KEY`

- Purpose: Operator key for stdio. Unused on HTTP/SSE, where each caller supplies a bearer.
- Lifecycle: Restart stdio after changing it. Hosted callers rotate their own bearer in the MCP host.
- Resolution: HTTP/SSE ignores it even when set. Stdio uses it. Absence is reported, never the value.
- Authority: Does not grant a caller another caller's identity.
- Evidence: Bring-your-own-key boundary. Inventory records presence only.

### `SIMBA_API_REQUEST_POLICY_JSON`

- Purpose: Optional deadlines and admission for the shared client.
- Lifecycle: Restart to change. Rollback is unsetting it.
- Resolution: Invalid JSON or fields fail startup. No numeric recommendation is implied by the parser.
- Authority: Operator only. Agent arguments cannot raise these ceilings.
- Evidence: Unset keeps the existing client timeout and retry loop and adds no admission.

### `SIMBA_API_MAX_ENCODED_BYTES`

- Purpose: Optional encoded response ceiling.
- Lifecycle: Restart to change. Rollback is unsetting it.
- Resolution: A positive integer, or unset. A caller max_response_bytes cannot raise it.
- Authority: Operator ceiling. It bounds the backend download, not MCP display alone.
- Evidence: Opt-in until a measured deployment selects a number.

### `SIMBA_API_MAX_DECODED_BYTES`

- Purpose: Optional decoded response ceiling.
- Lifecycle: Restart to change. Rollback is unsetting it.
- Resolution: A positive integer, or unset. Either byte setting fills the other when only one is set.
- Authority: Operator ceiling.
- Evidence: Opt-in until a measured deployment selects a number.

### `SIMBA_TOOL_DESCRIPTIONS`

- Purpose: Choose legacy or compact tool descriptions.
- Lifecycle: Read at server construction. Reconnect after changing it.
- Resolution: legacy or compact. No other value is accepted.
- Authority: Operator. Compact text does not grant tools or permissions.
- Evidence: No measured production default replaces legacy.

### `SIMBA_TOOL_PROFILE`

- Purpose: Fixed tool view. full and data_scientist expose the canonical catalogue.
- Lifecycle: Read at server construction unless --profile is passed. Reconnect after changing it.
- Resolution: --profile overrides a valid environment value. Invalid or empty environment values fail server import before the override.
- Authority: A profile hides tools. It does not grant backend permissions.
- Evidence: Shipped profiles are full, data_scientist, marketer and reviewer.

### `--profile`

- Purpose: Launch-time override of SIMBA_TOOL_PROFILE.
- Lifecycle: Applies to that CLI process only.
- Resolution: Wins over SIMBA_TOOL_PROFILE. Ignored by uvicorn simba_mcp.server:app.
- Authority: Operator launch configuration.
- Evidence: Same names as the environment variable.

### `--transport`

- Purpose: stdio, streamable-http or sse.
- Lifecycle: Launch argument. HTTP and SSE mark the process as a network transport.
- Resolution: uvicorn simba_mcp.server:app is a separate ASGI path and is always HTTP mode.
- Authority: Operator. Agents cannot switch transport.
- Evidence: stdio is the local default. Hosted deployment chooses a network transport explicitly.

### `--host`

- Purpose: Bind host for the CLI network transports.
- Lifecycle: Launch argument. The ASGI helper also passes 0.0.0.0 to disable localhost DNS-rebinding protection behind a proxy.
- Resolution: Does not apply to stdio or to the process manager's uvicorn bind.
- Authority: Operator.
- Evidence: Existing CLI default.

### `--port`

- Purpose: Bind port for the CLI network transports.
- Lifecycle: Launch argument. Uvicorn's own port is outside this flag.
- Resolution: CLI only.
- Authority: Operator.
- Evidence: Existing CLI default.

### `SIMBA_MCP_ALLOW_LOCAL_FILES`

- Purpose: Allow csv_path to read the server host filesystem.
- Lifecycle: Read on each local-file check. Restart workers that cached an old environment.
- Resolution: 1, true or yes allows. 0, false or no denies. Any other value follows the transport default.
- Authority: Operator. A caller cannot enable the server filesystem from a tool argument.
- Evidence: Network default is deny because the path is the server's, not the caller's.

### `SIMBA_MCP_METRICS`

- Purpose: Write structured metrics to stderr.
- Lifecycle: Read when an event is emitted. Rollback is unsetting it.
- Resolution: Only the exact value stderr enables the process sink. A task-local override wins for that task.
- Authority: Operator. Events must not include credentials.
- Evidence: Opt-in diagnostic. 1 and true do not enable it.

### `MCP_OAUTH_ENABLED`

- Purpose: Optional OAuth resource-server mode.
- Lifecycle: Read at server construction. Restart to change. Off leaves bring-your-own-key unchanged.
- Resolution: Any other value leaves it off. The server holds no OAuth client secret.
- Authority: Operator. Enabling it does not issue tokens.
- Evidence: Shipped off by default. Not a universal host feature.

### `SIMBA_PUBLIC_URL`

- Purpose: Issuer and resource base when OAuth mode is on.
- Lifecycle: Restart after changing it. Rollback with OAuth mode.
- Resolution: Ignored for authentication while MCP_OAUTH_ENABLED is off.
- Authority: Operator. It is a public URL, not a secret.
- Evidence: Required for a real hosted issuer. The localhost default is not a hosted recommendation.

### `MAX_UPLOAD_BYTES`

- Purpose: CSV ingest ceiling.
- Lifecycle: Code change and release. Not an environment variable.
- Resolution: Fixed. Proxy limits must allow at least the transport cap.
- Authority: Server-enforced.
- Evidence: Existing 10 MiB ingest limit.

### `MAX_REQUEST_BODY_BYTES`

- Purpose: MCP request body cap for CLI HTTP/SSE and the ASGI app.
- Lifecycle: Code change and release.
- Resolution: Fixed. Front proxies must allow at least this size or they reject the upload first.
- Authority: Server-enforced.
- Evidence: 12 MiB accommodates the 10 MiB ingest limit.

### `DEFAULT_TIMEOUT`

- Purpose: Client timeout when request policy is disabled.
- Lifecycle: Code change and release. Not selected as a new production policy.
- Resolution: Used only while SIMBA_API_REQUEST_POLICY_JSON is disabled.
- Authority: Server-enforced. Writes are not retried.
- Evidence: Existing client behaviour, retained by leaving policy unset.

## Per-call result arguments

`get_model_results` accepts `model_hash`, `sections`, `format`, `channels`, `max_grid_points`, `max_response_bytes`, `start`, `end`, `granularity`. `ctx` is framework context, not a caller setting.
`max_response_bytes`, when present, rejects an oversize MCP payload. It does not
limit the backend download and cannot raise `SIMBA_API_MAX_ENCODED_BYTES` or
`SIMBA_API_MAX_DECODED_BYTES`. Channel, grid, section and window arguments select
evidence. They are not operator configuration and they do not grant missing sections.

## Out of this inventory

Evaluation, benchmark and documentation commands have their own arguments and
provider credentials. Those credentials are not server configuration and are not
printed by this report. Guidance installation is a client workflow, not a server flag.
