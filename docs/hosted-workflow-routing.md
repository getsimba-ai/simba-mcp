# Optional hosted workflow recommendations

`recommend_workflow(request)` returns an advisory workflow category, canonical
guidance references and a shortlist of tools visible in the caller's current
catalogue. The external assistant chooses its subsequent calls and arguments.
The recommendation never executes a domain operation or establishes permission
or scientific acceptance.

Use it for unfamiliar intent where selecting a workflow would otherwise require
exploration. Skip it when the workflow is clear or its guidance is already loaded.
If it returns `fallback`, continue ordinary guidance and tool selection without
automatically retrying the recommendation.

## Data flow and authentication

The MCP forwards the caller's existing Simba bearer token to
`POST /api/v1/mcp/workflow-recommendations`. The backend authenticates the caller,
requires `read:models`, checks eligibility and reserves capacity before invoking
OpenAI Decisions. Session authentication follows existing backend conventions.
The OpenAI key belongs to the backend and is never returned to the MCP client.

The submitted intent is sent to OpenAI when the feature is enabled and the caller
is eligible. Supply only the intent needed for classification. The wrapper does
not send conversation history, model results or authentication material to the
provider. Intent is non-empty text bounded to 4,000 UTF-8 bytes. Customer
enablement requires the operator to verify the organisation's provider data
processing terms and region.

Question version `workflow-v1` selects among `mmm`, `results`, `priors`,
`optimiser`, `studies`, `var`, `campaigns`, `reporting`, `mixed_or_unclear` and
`unsupported`. Mixed intent asks for clarification. Provider refusal, invalid
answers, low confidence, unavailable admission and provider errors return bounded
fallbacks. Authentication and invalid-input errors retain normal API errors.

## Backend-owned configuration

These settings belong to the application backend, not the public MCP process:

| Setting | Default | Purpose |
| --- | --- | --- |
| `SIMBA_DECISIONS_ENABLED` | `false` | Explicit feature switch, `true` or `false` |
| `SIMBA_DECISIONS_OPENAI_API_KEY` | absent | Dedicated server credential |
| `SIMBA_DECISIONS_USER_IDS` | empty | Comma-separated eligible account IDs |
| `SIMBA_DECISIONS_DAILY_INPUT_TOKENS` | `100000` | Global daily reservation ceiling |
| `SIMBA_DECISIONS_RESERVE_INPUT_TOKENS` | `8000` | Conservative reservation per attempt, minimum 8000 |
| `SIMBA_DECISIONS_REQUESTS_PER_MINUTE` | `10` | Admission rate per account |
| `SIMBA_DECISIONS_CONFIDENCE` | `0.9` | Initial threshold, pending evaluation |

Redis admission is shared across workers. Each account has one active request;
using another API key does not create another account allowance. A validated
input-token count settles the reservation. Unknown billing remains reserved.
There are no automatic provider retries or classification caches. The daily
production token allowance is separate from an evaluation campaign's cumulative
monetary budget.

The provider deadline is two seconds, including pool waiting and streaming; the
backend deadline is three seconds. Requests use a dedicated reusable provider
pool. A client disconnect can stop the MCP wait after the backend has sent a
billable request. It cannot guarantee provider cancellation. Discard a result
whose original user request has been superseded.

## Compatibility and release order

The tool is additive and does not shrink an eagerly loaded catalogue. Suggestions
intersect the operator catalogue and effective role profile; hidden tool names
are omitted and missing coverage sets `profile_limited`. Profiles describe tool
presentation; backend permissions remain authoritative.

The backend imports the focused public routing contract. Deploying it therefore
requires a verified package containing that contract. Test the exact source
candidate first, publish the approved MCP version, verify the published artifact,
then update the application's exact pin and test its deployment. A source branch
or passing mock test is not evidence of publication or client acceptance.

To stop paid admission, set `SIMBA_DECISIONS_ENABLED=false` and apply the setting
through the backend's deployment process. Existing tools remain usable and the
recommendation returns fallback. Do not replay interrupted provider calls. If the
additive catalogue causes a client compatibility problem, restore the verified
previous package and application revisions and reconnect the affected clients.

## Evaluation boundary

Contract tests establish response validation and isolation. Routing precision
requires frozen independently labelled examples. Speed and token claims require
paired complete-task comparisons including selector cost, backend round trips,
guidance calls, main-agent turns and billed failures. Named-client adoption and
scientific acceptance remain separate. No benefit is implied by exposing this
tool, and no paid run is authorised by this document.
