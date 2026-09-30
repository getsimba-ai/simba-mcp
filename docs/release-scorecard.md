# Proposed 0.13.0 release scorecard

This is a proposed release, not a released or deployed version. Current selection
has not demonstrated an accepted quality, latency or cost improvement. The routing
correction passed its small development check in both arms; a new
selection comparison is being prepared with explicit model identifiers.

## Scope and defaults

| Area | Release decision |
| --- | --- |
| Existing tool access | Full catalogue and legacy descriptions remain default. Compact descriptions, fixed role profiles and host-specific discovery remain opt-in. |
| Results | Explicit channel and grid selection disclose `_mcp_selection`, preserve unfiltered defaults and avoid mutating source results. Canonical channel mappings establish display-name identity. Existing sections and windows remain the retrieval interface. |
| Download bounds | Encoded and decoded response ceilings are opt-in. Default compression compatibility is retained. Local result filtering does not reduce backend download by itself. |
| Request policy | End-to-end deadlines, bounded admission, caller fairness and bounded read retries are opt-in. Mutation retry behaviour is unchanged. Cancellation releases local capacity; it does not prove backend job cancellation. |
| Telemetry | Optional numerical stderr observations exclude credentials and raw data. Tool timing excludes the hosted preference lookup; whole-request timing is needed for user latency. |
| User preference | Hosted users choose Full, Data scientist, Marketer or Reviewer in Profile > Connected apps. Full is the default. Selection narrows the operator catalogue and grants no permissions; Reviewer is not read-only. |
| Configuration | The generated inventory and secret-free diagnostic cover ownership, effective values and validation. No numerical production policy is recommended from synthetic tests. |
| Deferred work | No additional summary tool or general discovery cache. Existing selectors and full access remain available. Backend projection benefit is not established by local filtering. |

Compact descriptions, Skills, discovery and fixed role profiles predate this
release. Their continuing availability is not a new performance claim.

## Evidence and limitations

| Evidence | Outcome |
| --- | --- |
| Historical Grok role-profile comparison, 24 sessions | Full supported 12/12; Reviewer supported 11/12. Point cost saving 17.9%, confidence interval -10.9% to 34.1%; p95 latency increased 33.7%. Rejected. |
| Stopped selective-result comparison, first four sessions | All four failed the frozen zero-discovery policy. Numerical answers were supported; no unsupported material claims or unauthorised actual effects. The prompt did not explicitly distinguish a model name from its hash, so those discovery calls are not proven product defects. Cost US$0.431480; remaining sessions were not run. |
| Routing development comparison, four sessions | Both control and candidate passed 2/2. Each used one bounded result read; one control also retrieved supplied guidance. Cost US$0.326834. This exposed-case check establishes no comparative reliability or performance improvement and inherits the identifier wording limitation. |
| Synthetic request admission, non-overload case | Both configurations completed 24/24 requests. Peak backend concurrency fell from 24 to 4, while p95 increased from about 164 ms to 326 ms. This supports an explicit reliability trade-off, not a latency improvement claim. |
| Server checks | The routing correction at `e92bea9` passed 650 local tests. Final source CI, independent review and installed-artifact verification remain required. |
| Application integration checks | The staging-based application change passed 16 focused Python tests, five UI tests and TypeScript checking. Actual canonical API-key and OAuth resolvers, SQLite preference persistence and an in-process MCP SDK bridge verify per-user listing and excluded-call refusal. These are separate application-source tests, not deployed-server evidence. |
| Browser usability | A synthetic fixture using the actual shared Profile tabs and Connected apps panel passed at mobile, tablet and desktop widths. Other profile panels were placeholders. |

Independent task review requires future known-identifier prompts to state `model_hash` explicitly. Name-only tasks need realistic permitted discovery and are not covered by that known-identifier contract. The original grades and stopped decision remain unchanged.

Historical experiments retain their original grades, source versions and limits.
They are not pooled across providers or relabelled as final acceptance. The custom
Grok Responses host exercises real tool dispatch against synthetic backends. The
historical Haiku Messages discovery pilot certifies only its recorded host/model
combination. Claude desktop, Claude Code and other remote clients are not certified
by those experiments. No authenticated deployed canary has been performed here.

See [native discovery support](native-discovery.md#support-matrix),
[configuration](configuration.md), [profiles](tool-profiles.md),
[performance measurement](performance.md) and [deterministic evaluation](evaluation.md).

## Coordinated upgrade and rollback

1. Complete prospective evaluation, independent reviews, current-head CI and the
   clean installed-package checks. Finalise this scorecard against the release commit.
2. Publish and verify the 0.13.0 distribution, including packaged guidance and
   configuration resources. Then update the application's dependency pin from
   0.12.0 to 0.13.0 and validate the shared application/MCP image.
3. The matching application and MCP contract requires an additive user-preference
   migration and the new endpoint. Hosted `tools/list` and `tools/call` require a
   bearer and the schema-version-1 preferences endpoint even when OAuth mode is
   disabled. Missing endpoints and failed lookups refuse requests. There is no
   older-backend fallback. This preference middleware does not change `initialize`;
   OAuth resource-server mode retains its own authentication boundary.
4. Obtain separate authority for the named hosted deployment and bounded canary.
   Only then apply the migration, start the matching versions and run the canary.
   Verify ownership, reconnect, excluded-call refusal, inactive/revoked credential
   rejection and whole-request latency. Local tests do not satisfy this gate.
5. Prepare rollback to a previously verified matching application and MCP image.
   Retain the additive preference column and saved choices; do not automatically
   run its down migration. A rollback to 0.12.0 restores the previous catalogue
   behaviour and does not enforce saved user profiles. Reconnecting does not undo
   submitted operations.

Package publication, application deployment and epic closure are distinct gates.
The release is not operationally accepted until the authorised canary and rollback
exercise succeed. Scientific MMM validation requires a separate follow-up decision; engineering
fixtures do not establish it.
