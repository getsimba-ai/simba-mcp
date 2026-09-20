# Simba MCP Server

[![PyPI](https://img.shields.io/pypi/v/simba-mcp)](https://pypi.org/project/simba-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

[Simba](https://simba-mmm.com) is a Bayesian Marketing Mix Modeling (MMM) platform. This Marketing Mix Modeling [MCP server](https://modelcontextprotocol.io/) lets AI assistants interact with your models directly â€” upload data, build models, check results, and run budget optimizations through natural language in Claude, Cursor, or Claude Code.

## Installation

```bash
pip install simba-mcp
```

Or run directly without installing:

```bash
uvx simba-mcp
```

## Quick Start

### Cursor IDE

Add to your Cursor MCP settings (`.cursor/mcp.json` in the workspace or global settings):

```json
{
  "mcpServers": {
    "simba": {
      "command": "uvx",
      "args": ["simba-mcp"],
      "env": {
        "SIMBA_API_URL": "https://demo.simba-mmm.com",
        "SIMBA_API_KEY": "simba_sk_..."
      }
    }
  }
}
```

### Claude Code

Add to your Claude Code MCP config:

```json
{
  "mcpServers": {
    "simba": {
      "command": "uvx",
      "args": ["simba-mcp"],
      "env": {
        "SIMBA_API_URL": "https://demo.simba-mmm.com",
        "SIMBA_API_KEY": "simba_sk_..."
      }
    }
  }
}
```

### Claude API (MCP Connector)

Use the remote Streamable HTTP transport with the Anthropic MCP connector:

```python
import anthropic

client = anthropic.Anthropic()

response = client.beta.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    messages=[{"role": "user", "content": "List my Simba models"}],
    mcp_servers=[
        {
            "type": "url",
            "url": "https://demo.simba-mmm.com/mcp",
            "name": "simba",
            "authorization_token": "simba_sk_...",
        }
    ],
    tools=[{"type": "mcp_toolset", "mcp_server_name": "simba"}],
    betas=["mcp-client-2025-11-20"],
)
```

## Available Tools

| Tool | Description |
|------|-------------|
| `get_data_schema` | Get the canonical CSV schema for MMM input files |
| `list_recipe_drafts` / `get_recipe_draft` | Inspect authoring drafts and complete versioned snapshots on supporting backends |
| `create_recipe_draft` / `update_recipe_draft` | Save complete draft state with retry identity and optimistic concurrency; no publication or fit |
| `upload_data` | Upload a CSV dataset to Simba |
| `list_uploads` | List previously uploaded datasets |
| `get_upload` | One upload's details, including its column schema |
| `list_models` | List all models with their status |
| `create_model` | Configure and start fitting a new MMM model |
| `get_model` | Model metadata + config echo â€” works for any status, incl. failed |
| `delete_model` | Permanently delete a FAILED model (409 for any other status) |
| `rename_model` | Rename a model without saving it |
| `save_model` | File a model into a project (makes it visible to default `list_models`) |
| `unsave_model` | Release a saved model's slot (non-destructive inverse of `save_model`) |
| `list_projects` | List the projects (model folders) you can file models into |
| `create_project` | Create a named project, optionally team-shared |
| `rename_project` | Rename a project you own |
| `get_model_status` | Poll fitting progress and optional heartbeat/stall-threshold metadata |
| `get_model_results` | Get results (ROI, contributions, response curves, diagnostics, and more) |
| `create_var_model` | Fit a long-term (VAR) model |
| `link_var_model` / `unlink_var_model` | Attach/detach a VAR model to an MMM for the `long_run_rollup` section |
| `set_contribution_groups` / `get_contribution_groups` | Persist/read the contributions-view driver groupings |
| `run_optimizer` | Run budget optimization on a completed model |
| `get_optimizer_results` | Get optimizer status and results (latest, or a specific `run_id`) |
| `get_scenario_template` | Generate a forward-period template for scenario planning |
| `run_scenario` | Run a "what-if" scenario prediction |
| `get_scenario_results` | Get scenario results (latest, or a specific `run_id`) |
| `list_runs` | List a model's saved optimizer/scenario run history |
| `update_run` | Rename/annotate a saved run (notes, tags) |
| `set_run_pinned` | Pin/unpin a saved run |

## Example Prompts

Try these with any connected AI assistant:

**Explore your models:**
> "List my Simba models and show me the channel ROI summary for the most recent complete model."

**Build a model:**
> "Upload this CSV data to Simba and create a new MMM model with TV, Search, and Social as media channels. Use 'revenue' as the KPI and 'date' as the date column."

**Check progress:**
> "What's the fitting status of model a1b2c3d4?"

**Get results:**
> "Show me the model diagnostics and channel contributions for model a1b2c3d4."

**Optimize budget:**
> "Run a budget optimization on model a1b2c3d4 with $1M total budget over 12 months. Set TV bounds to 5-40% and Search to 10-50%. Use uniform laydown weights."

**Response curves:**
> "Show me the response curves for model a1b2c3d4. At what spend level does TV hit diminishing returns?"

**Scenario planning:**
> "Get a scenario template for model a1b2c3d4 for the next 12 weeks. Then run a scenario where I increase TV by 20% and cut Search by 10%. What happens to revenue?"

**Full workflow:**
> "I have marketing data I want to analyze. First get the schema so I know what format is needed, then upload my data, create a model, and once it's done show me the ROI by channel."

## Agent Skills

The [`skills/`](skills/) directory ships workflow skills in the
[Agent Skills](https://agentskills.io) format (`SKILL.md` per skill) â€”
install them into any skills-aware agent (e.g. Claude Code) alongside this
MCP server:

| Skill | Covers |
|---|---|
| [`simba-mmm-workflow`](skills/simba-mmm-workflow/SKILL.md) | Upload â†’ create â†’ poll â†’ reading results correctly (section semantics, channel naming, attribution/Overlap rules, context-size controls) |
| [`simba-optimizer-runs`](skills/simba-optimizer-runs/SKILL.md) | Optimizer payload conventions, revenue vs profit, polling by run_id, decision- vs comparison-column semantics, run curation |
| [`simba-prior-conventions`](skills/simba-prior-conventions/SKILL.md) | Prior-override payloads: smart-default merging, strict rejection, the half-saturation / half-marginal / half-life anchor families |
| [`simba-var-workflow`](skills/simba-var-workflow/SKILL.md) | Long-term (VAR) modeling: create â†’ poll â†’ link â†’ long_run_rollup |

The skills are documentation artifacts â€” they ride the repo, not the wire
protocol.

## Gotchas & Tips

Things that commonly trip up both AI agents and humans:

### Hosted server: your bearer token IS your login

On HTTP deployments each request is authenticated with the caller's own
`Authorization: Bearer simba_sk_...` token â€” there is no server-side shared
key. If tool calls return `"No API key on this request"`, your MCP client
isn't sending the token (check the `authorization_token` / headers setting
in its config).

### Channel names are exact-match

Model results are keyed by the channel's **activity column** name (e.g. `"search_activity"`, `"TV_impressions"`), **not** by the `channels[].name` you passed to `create_model`. Keys can contain spaces and matching is **case-sensitive and space-sensitive** â€” the optimizer and scenario tools use them as dictionary keys.

**Always** call `get_model_results` with `sections="channel_summary"` first to see exact channel keys, then use those verbatim in optimizer/scenario payloads.

### Results sections

`get_model_results` serves these sections (request only what you need via `sections=`):
`channel_summary`, `contributions` (KPI/unit space â€” multiplier **not** applied), `coefficients` (per-period per-channel **revenue** table), `params`, `decay_curves`, `response_curves`, `marginal_curves`, `saturation`, `mroi_summary` (marginal ROI at current spend with 94% HDI; post-#591 fits add the `allperiods_unweighted` / `spendweighted_active` convention scalars, and post-#629 fits add a `*_mean` beside every `*_median` â€” the median is displayed, the mean is what reconciles with the marginal-revenue curve), `mroi_periods` (**opt-in only** â€” the per-period marginal ROI series; never in the default payload, request it by name), `model_stats`, `actual_vs_model`, `long_run_rollup`, `optimizer`, `predictions`, `posterior`, `financials`, `model_config`. The response's `sections_available` field is authoritative if the server is newer than these docs.

### Models are identified by `model_hash`

All model endpoints use the string `model_hash` (e.g. `"f835671a25"`) returned by `create_model` and `list_models`.

### API-key management is deliberately not exposed

The `/api/v1/keys` endpoints (create/list/revoke API keys) are session-auth only and have no MCP tools **by design**: a server holding one key must not be able to mint or revoke keys. Manage keys in the Simba UI (Profile â†’ API Keys).

### Optimizer arrays, not scalars

`laydown_weights` and `period_cpm` must be **objects of arrays**, each array having exactly `num_periods` elements:

```json
// Wrong
"period_cpm": {"TV": 10}

// Correct
"period_cpm": {"TV": [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10]}
```

The same channel keys must appear in `bounds`, `laydown_weights`, and `period_cpm`. Bounds values are **percentages** (0-100) of `total_budget`, not currency amounts.

### Clean NaN from scenario templates

The template from `get_scenario_template` may contain `NaN`/`null` for channels without historical data. Replace them with `0` before passing to `run_scenario`:

```python
import math
for row in scenario_data:
    for key, val in row.items():
        if val is None or (isinstance(val, float) and math.isnan(val)):
            row[key] = 0
```

### Three endpoints are async

These return 202 and require polling:

| Action | Start | Poll |
|--------|-------|------|
| Fit model | `create_model` | `get_model_status` |
| Optimize | `run_optimizer` | `get_optimizer_results` |
| Scenario | `run_scenario` | `get_scenario_results` |

Poll every 5-10 seconds. Check the `status` field for `"complete"` or `"failed"`.

### Data upload requirements

- **CSV only** (not Excel). Maximum **10 MB** (API-enforced).
- Row minimum: check `get_data_schema` â†’ `x-simba-constraints.min_rows`; the upload response's `warnings` field is authoritative. More rows = tighter posteriors (104+ weekly rows recommended).
- Media columns: `{channel}_activity` and `{channel}_spend` per channel.
- Use `0` for inactive periods, not blank or NA.
- Large file? Pass `csv_path` (a local file path) instead of `csv_content` â€” the server reads it directly instead of the CSV going through the conversation. Local (stdio) servers only; disabled on HTTP/SSE deployments unless `SIMBA_MCP_ALLOW_LOCAL_FILES=1`.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Authentication required` | No API key or expired key | Check `SIMBA_API_KEY` env var |
| `API key missing required scope: <scope>` | Key doesn't have the needed scope | Create a key with all scopes |
| `Missing required fields: [...]` | Payload missing required keys | Check the tool's parameter list |
| `Model status is '<status>'. Optimization requires a 'complete' model.` | Model still fitting or failed | Poll `get_model_status` until complete |
| `laydown_weights['TV'] must be an array of length 12` | Scalar instead of array, or wrong length | Use arrays matching `num_periods` |
| `period_cpm['TV'] values must all be positive` | Zero or negative CPM | All CPM values must be > 0 |
| `Channels in bounds missing from period_cpm: [...]` | Mismatched channel names | Same keys in bounds, laydown_weights, and period_cpm |
| `Columns not found in data: [...]` | Column name typo | Check CSV headers match exactly |
| `File exceeds 10 MB limit` | CSV too large | Reduce file size or aggregate data |

## Direct API Access

The MCP server wraps the Simba REST API. For scripting, CI/CD, or environments without MCP, you can call the API directly.

### When to use MCP vs direct API

| | MCP (via AI assistant) | Direct API (curl / Python) |
|---|---|---|
| **Best for** | Exploratory analysis, conversational workflows | Automated pipelines, scheduled jobs, scripts |
| **Async polling** | Assistant handles it automatically | You implement poll-until-complete logic |
| **Data cleaning** | Assistant cleans NaN/null, builds payloads | You write the data prep code |
| **Reproducibility** | Conversational | Scriptable, version-controlled |

Both use the same API keys with the same scopes.

### Quick start (Python)

```python
import requests, time

BASE = "https://demo.simba-mmm.com"
HEADERS = {"Authorization": "Bearer simba_sk_..."}

# Upload data
with open("marketing_data.csv", "rb") as f:
    r = requests.post(f"{BASE}/api/v1/ingest",
                      headers={**HEADERS, "Content-Type": "text/csv"},
                      data=f.read(), params={"name": "q1_data"})
file_id = r.json()["id"]

# Create model
r = requests.post(f"{BASE}/api/v1/models", headers=HEADERS, json={
    "data_source": {"uploaded_file_id": file_id},
    "date_column": "date",
    "kpi_column": "revenue",
    "hierarchy_column": "brand",
    "channels": [
        {"name": "TV", "activity_column": "tv_grps", "spend_column": "tv_spend"},
        {"name": "Search", "activity_column": "search_impressions", "spend_column": "search_spend"},
    ],
    "total_media_effect": "Retail",
})
model_hash = r.json()["model_hash"]

# Poll until complete
while True:
    status = requests.get(f"{BASE}/api/v1/models/{model_hash}/status",
                          headers=HEADERS).json()
    if status["status"] in ("complete", "failed"):
        break
    print(f"Fitting... {status.get('progress', '?')}%")
    time.sleep(10)

# Get results
results = requests.get(f"{BASE}/api/v1/models/{model_hash}/results",
                       headers=HEADERS,
                       params={"sections": "channel_summary,model_stats"}).json()
for ch in results["results"]["channel_summary"]:
    print(f"{ch['Channel']}: ROI {ch['ROI']:.1f}")
```

### Quick start (curl)

```bash
API_KEY="simba_sk_..."
BASE="https://demo.simba-mmm.com"

# Upload data
curl -X POST "$BASE/api/v1/ingest?name=q1_data" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: text/csv" \
  --data-binary @marketing_data.csv

# Create model (replace uploaded_file_id with id from upload)
curl -X POST "$BASE/api/v1/models" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"data_source": {"uploaded_file_id": 1}, "date_column": "date", "kpi_column": "revenue", "hierarchy_column": "brand", "channels": [{"name": "TV", "activity_column": "tv_grps", "spend_column": "tv_spend"}]}'

# Poll status (replace MODEL_HASH)
curl "$BASE/api/v1/models/MODEL_HASH/status" -H "Authorization: Bearer $API_KEY"

# Get results
curl "$BASE/api/v1/models/MODEL_HASH/results?sections=channel_summary,model_stats" \
  -H "Authorization: Bearer $API_KEY"
```

## API Key Setup

The MCP server authenticates with the same API keys used by the Simba REST API. Create a key with the required scopes:

1. Go to **Profile > API Keys** in the Simba UI
2. Click **Create Key**
3. Set scopes: `ingest`, `read:models`, `read:results`, `create:models`, `optimize`, `scenario`
4. Copy the key (shown only once)

How the key is supplied depends on where the server runs:

- **Local (stdio â€” Cursor, Claude Code):** set it as the `SIMBA_API_KEY`
  environment variable in your MCP config (the examples above).
- **Hosted (`https://demo.simba-mmm.com/mcp`):** send it as the HTTP
  `Authorization: Bearer` header â€” the `authorization_token` field in the
  Claude MCP connector config. **Every caller uses their own key** (v0.2.2+):
  the server never shares an identity between callers, a request without a
  key gets a structured 401 with guidance, and you only ever see your own
  account's models.

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `SIMBA_API_URL` | Simba API base URL | `http://localhost:5005` |
| `SIMBA_API_KEY` | Your Simba API key (stdio mode only â€” HTTP callers send their own key as the bearer token) | (required for stdio) |

## Transport Modes

The server supports all MCP transport modes:

```bash
# stdio (default) â€” for Cursor, Claude Code
simba-mcp

# Streamable HTTP â€” for remote deployment
simba-mcp --transport streamable-http --port 8100

# SSE â€” legacy transport
simba-mcp --transport sse --port 8100

# Or via uvicorn directly
uvicorn simba_mcp.server:app --host 0.0.0.0 --port 8100
```

## License

MIT


### Fit heartbeat visibility

On backends that support it, `get_model_status` also returns `fit_liveness`.
The MCP server passes the response through unchanged; older backends may omit
this field. With `available: true`, `heartbeat_age_seconds`,
`stall_timeout_seconds`, and `seconds_until_stall_threshold` are in seconds;
`last_heartbeat_at` is a Unix timestamp in seconds. `stall_threshold_exceeded`
reports whether heartbeat age is strictly greater than the configured threshold.

The countdown is to a stale-heartbeat threshold, not completion ETA or an exact
termination time: the watchdog runs periodically. It does not change `status`.
With `available: false`, `reason` is `heartbeat_unavailable` (including unavailable
heartbeat storage) or `not_fitting`. Missing or unavailable metadata is unknown,
not evidence that a fit is healthy or stalled. Continue polling with backoff and
use the reported model status; do not automatically restart or duplicate a fit.
### Explicit control priors and transforms

Use `control_columns` to include controls and optional `control_priors` to
configure them. Overrides select an exact column via `control`; media `priors`
continue to select a channel via `channel`.

```json
{"control_columns": ["price", "discount_depth"], "control_priors": [
  {"control": "price", "transform": "LOG", "distribution": "normal", "mean": -1, "sd": 0.5},
  {"control": "discount_depth", "transform": "N", "distribution": "normal", "mean": 1, "sd": 0.5}
]}
```

These are illustrative coefficients, not fitted estimates or recommended priors.
Native transforms: N = x; DM = x/mean(x); STA = x/sample_sd(x) without centering;
DDM = x/mean(KPI); LOG = log(x/mean(x)), requiring positive x.
Under a log link, a LOG coefficient is an elasticity; N is a semi-elasticity.
Changing a transform does not convert prior units: explicitly choose suitable
coefficient priors. Normal and inversegamma use mean/sd (positive mean for
inversegamma); truncatednormal also requires ordered lower/upper bounds;
halfnormal uses only sd. Unused fields, unknown keys, null field values and
nonselected/duplicate controls are rejected. Omitted fields preserve applicable
smart defaults; changing family clears inapplicable bounds/mean.

Nonempty overrides preflight `get_data_schema` for
`x-simba-model-capabilities.control_priors` version 1 and all five transforms.
Unsupported, malformed or unavailable capability checks stop before creation;
never retry by removing requested settings. Omitted/None/empty overrides keep
legacy calls unchanged. Backend support must be deployed before using this
option. Direct REST clients must perform the same capability check and put
`control_priors` at the request root. Check `get_model`'s resolved priors and
`overridden_fields` after creation. Prediction uses existing fit-time constants;
this feature does not change preprocessing split order or fit a model for you.

### Study workflows

The study tools require a Simba backend with the workflow API deployed. Studies
belong to projects and provide a shared record for analysts and agents:

- Create/read/update studies with declared questions, attempt limits and concurrency limits.
- Validate, save and inspect immutable recipe revisions; list recipes captured by the wizard.
- Launch a revision with a declared quality policy and caller-generated submission key.
- Inspect progress, request cancellation, evaluate saved evidence and compare candidates.
- Preview/import existing models and record recommendations with a rationale.

Reuse the same submission key when retrying an uncertain launch; changing the
recipe or policy requires a new key. Workflow writes are sent once, without
automatic HTTP retries. A study does not autonomously launch its budget of fits.
Its runs use the existing models, workers and progress records.

Project sharing permits reading studies; mutations require ownership. The MCP
can recommend but cannot record analyst acceptance. Imported historical recipes
are review-only where original provenance is incomplete. Wizard-captured recipes
can be inspected and launched; changing a captured wizard configuration requires
another wizard capture or a separately validated API recipe.

Quality reports distinguish failed checks, missing evidence and required analyst
review. Current saved-window error metrics and R-hat are not held-out validation
or proof of business validity. No tool automatically promotes a winning model.


## Discovery and reliable Studies workflows

Start with `get_backend_capabilities` to read the connected backend's model,
transform/prior and workflow advertisements. Missing fields mean **unknown**;
installing this package does not upgrade the backend. All tool annotations are
informational hints, never permission checks.

For Studies: inspect the project/study budget, validate a recipe, freeze a revision,
declare a quality policy, then launch with an explicit submission key. Preserve
that key and the exact inputs after an uncertain response. Poll the shared run;
requested cancellation is not confirmed completion. Reload and reconcile on 412;
revalidate on an input-hash conflict. Optional `expected_content_hash` on recipe
create/revise binds the validated effective inputs. Evaluate existing evidence and
recommend with limitations; analyst acceptance remains in the frontend. Missing
evidence never passes, and fitted-window metrics are not holdout validation.

Writes are sent once, without automatic retries. Reconcile uncertain mutations
before repeating them. Reads retain bounded transient retries. Existing error
objects retain `error` / `_status_code`, with additive `_error_code` and
`_next_action` guidance. Backend additive fields remain intact in structured output.

For bounded results, request `sections="channel_summary,model_stats"` first and use
`channels` / `max_grid_points` where appropriate. Optional `max_response_bytes`
returns an actionable 413 instead of partial evidence when the filtered JSON
payload is too large. It bounds payload serialization, not backend download or MCP
envelope overhead. Existing defaults remain unchanged.

See [architecture and compatibility](docs/architecture.md) for ownership,
transport/authentication boundaries, known limits and validation.

Draft authoring discovery: `get_recipe_draft_template(family="mmm" | "var")` returns complete defaults generated by the shared wizard, a template hash and the draft envelope schema. Start new drafts from this snapshot and preserve unedited fields. Defaults are not validated models; check publication capabilities before publishing. Requires the corresponding backend capability and `read:models`.

Pass either `uploaded_file_id` or `pipeline_version_id` to `get_recipe_draft_template` to copy an owned uploaded dataset or saved pipeline output version into the new authoring snapshot and populate its bounded preview. Optional source origin is verified by the backend against exact bytes; detail responses include a source manifest. Reopening uses frozen data even if the original upload disappears. This does not enable publication or model fitting.

Draft publication: `publish_recipe_draft` freezes a saved MMM or VAR draft as an atomic batch, using expected version and caller UUID recovery; it never launches a fit. `get_recipe_revision_authoring` retrieves the immutable authoring snapshot for copying to a new draft. Check backend publication capabilities. When `publication_constraints.automatic_prior_resolution` is `freeze_at_publication`, automatic MMM priors are resolved once and replayed without rebuilding. Original authoring choices remain recoverable for editing a new draft. This applies to draft publication; legacy `api_mmm` recipe resolution still requires fixed priors. VAR preserves its raw input and engine manifest; MMM quality policies cannot establish VAR acceptance.

Calibration: check the backend `calibration` capability. MMM draft publication validates active likelihood observations and returns their count, units, channels and hash in recipe provenance. Enabled invalid or unapplied observations fail explicitly; VAR calibration is unsupported. Preserve disabled authoring rows when editing. Imported wizard JSON is retained as editable rows; multipart wizard CSV capture retains its original bytes. No new MCP route is needed.

Pipeline sources retain the exact version ID, pipeline ID, version number and verified content hash. No pipeline is executed. Existing exported uploads are not assigned inferred pipeline lineage.

Draft `source.history` preserves up to 100 recorded column transformations/removals with parameters and before/after data hashes. The backend checks chain continuity and the terminal data hash. These are client-reported authoring records, not independently replayed operations or quality evidence. Edited data must omit an unchanged source origin. Unknown nested fields remain preserved.

Optional `calibration_import` retains an original JSON file (1 MB maximum) in the authorized authoring snapshot. Preserve it independently of current editable observations. The backend verifies its bytes/hash; published provenance includes filename/hash and explicitly states current observations may differ. Ordinary recipe responses omit the raw attachment. This reference is not scientific validation.


Custom numeric quality checks: `create_quality_policy` accepts checks such as
`{"metric":"custom:benchmark_deviation","name":"Benchmark deviation","units":"%","operator":"lte","maximum":10,"required":true}`.
Use `gte` with `minimum`, or `between` with both inclusive bounds. Read backend capability discovery before using this additive contract.

For externally calculated metrics, call `evaluate_study_run(run_id, policy_id)` first and retain `report.basis_hash`. Calculate from that run's saved outputs, then call the same tool with `expected_basis_hash` and `external_evidence=[{"metric":"custom:benchmark_deviation","value":8,"method":"Absolute deviation as percentage of benchmark","source_reference":"Versioned model export and benchmark"}]`. An optional `source_sha256` records a reported source digest. The backend determines pass/fail and rejects stale output bases. Every submission creates a new assessment and must supply all intended custom values; omitted values remain unevaluated. Source references and calculations are submitter-reported, not independently verified. This numeric MMM contract does not execute agent code, accept a model, support VAR acceptance, or designate a champion.


Boolean checks use `kind: "boolean"`, `operator: "equals"` and strict boolean `expected`. Submit a JSON boolean in `external_evidence.value`; numeric or string substitutes are rejected. Manual checks use `kind: "manual"`, `operator: "equals"`, `expected: true`. MCP can define these rules and read evidence, but API keys cannot submit manual sign-off: a signed-in reviewer must supply confirmation, rationale and source through the frontend. Missing answers stay unevaluated; sign-off is not automatic model acceptance or champion selection.


`get_study_champion(study_id)` reads the incumbent, accepted candidates/eligibility blockers and immutable selection/replacement/revocation history. The backend requires migration `workflow_champion_001`. Writes require the project owner's frontend session; MCP cannot promote or revoke. Stale evidence retains the incumbent with review_required. Validation references are reviewer-declared and `decision_grade_ready` remains false until scientific protocol qualification is implemented. Champion designation does not deploy or fit a model.


Native prediction-window gates are available as `prediction_mae`, `prediction_rmse` and `prediction_wape` (WAPE is a fraction). They use the existing create_quality_policy/evaluate_study_run tools. The backend reads saved actual/prediction rows, requires unique prediction dates after the saved training window and leaves missing/malformed evidence unevaluated. Both windows are bound into the assessment hash. This does not prove untouched holdout provenance, leakage-free preprocessing or full sampling intent; decision-grade champion qualification remains separate.


`create_quality_policy(..., validation_protocol=...)` can declare a temporal holdout before launching both runs. Required protocol fields are training_end, prediction_start/end, min_draws, min_tune, min_chains, max_r_hat and max_prediction_wape. Use `kind: "temporal_holdout"`; dates are ISO and WAPE a fraction. No defaults are recommended. Both runs must launch under that exact policy.

`assess_study_validation_pair(study_id, full_run_id, validation_run_id, policy_id)` reads saved evidence without fitting or writing a decision. It checks distinct completed MMM tasks, launch binding, matching frozen files/settings/runtime, configured sampling minima, R-hat, prediction-window WAPE/dates and full-date coverage. Missing evidence blocks. The response fingerprint identifies the assessed records. Passing compatibility does not verify retained draws/ESS/divergences, preprocessing or untouched holdout history, and decision_grade_ready remains false.

Validation-pair responses include `sampling_evidence` for the full and validation runs: retained chain/draw counts, bulk/tail ESS minima and divergences when saved by the fitting engine. Missing or partial records are explicit. These values are not yet checked against acceptance limits and do not certify scientific readiness.

Protocols may now opt into `retained_sampling: {min_ess_bulk, min_ess_tail, max_divergences}` before launching both models. All limits are explicit, with positive ESS minima and a nonnegative integer divergence maximum. Pair assessments also apply declared chain/draw minima to retained counts. Missing/partial native records block; `sampling_qualification` distinguishes pass, blocked and not_declared. Business validity and holdout provenance still prevent scientific certification.

Set `validation_protocol.require_policy_review` before launching to require current analyst acceptance of each latest launch-policy assessment in pair checks. Stale evidence, subsequent rejection, missing acceptance or ambiguous ordering blocks. This reuses required policy gates; external business calculations remain reported evidence. MCP can declare and read these requirements but cannot supply analyst acceptance.

Pair responses expose `holdout_provenance` separately from compatibility. Version 1 full-input preprocessing records remain blocked. Version 2 records identify training-only transformation/scaling and report `review_required` with `preprocessing_status: training_only`. Missing or unsupported records are unavailable; no record is silently certified. Prior-source independence and holdout access/reuse evidence remain required; `decision_grade_ready` stays false. Existing routes and tool arguments are unchanged.

Pair responses also expose `prior_provenance`: native frozen automatic-prior source windows are checked against the declared training end and bound to recipe input hashes. A later source window or mismatched hashes is blocked; missing historical/uploaded provenance is unavailable. A valid window still requires review of assumptions, external calibration and holdout reuse. This does not record access history or certify independence. No tool arguments or routes changed.
