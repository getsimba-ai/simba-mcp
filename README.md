# Simba MCP Server

[![PyPI](https://img.shields.io/pypi/v/simba-mcp)](https://pypi.org/project/simba-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

[Simba](https://simba-mmm.com) is a Bayesian Marketing Mix Modeling (MMM) platform. This [MCP server](https://modelcontextprotocol.io/) lets AI assistants interact with your Marketing Mix Models directly — upload data, build models, check results, and run budget optimizations through natural language in Claude, Cursor, or Claude Code.

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
        "SIMBA_API_URL": "https://app.simba-mmm.com",
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
        "SIMBA_API_URL": "https://app.simba-mmm.com",
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
            "url": "https://app.simba-mmm.com/mcp",
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
| `upload_data` | Upload a CSV dataset to Simba |
| `list_models` | List all models with their status |
| `create_model` | Configure and start fitting a new MMM model |
| `get_model_status` | Poll fitting progress for a model |
| `get_model_results` | Get results (ROI, contributions, response curves, diagnostics, and more) |
| `run_optimizer` | Run budget optimization on a completed model |
| `get_optimizer_results` | Get optimizer status and results |
| `get_scenario_template` | Generate a forward-period template for scenario planning |
| `run_scenario` | Run a "what-if" scenario prediction |
| `get_scenario_results` | Get scenario prediction results |

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

## Gotchas & Tips

Things that commonly trip up both AI agents and humans:

### Channel names are exact-match

Channel names in model results can contain spaces (e.g. `"Digital impressions"`, `"TV_impressions"`). The optimizer uses these as dictionary keys — matching is **case-sensitive and space-sensitive**.

**Always** call `get_model_results` with `sections="channel_summary"` first to see exact channel names, then use those verbatim in optimizer payloads.

### Models are identified by `model_hash`

All model endpoints use the string `model_hash` (e.g. `"f835671a25"`) returned by `create_model` and `list_models`.

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

- **CSV only** (not Excel). Maximum 50 MB.
- Minimum **52 rows** (104+ recommended).
- Media columns: `{channel}_activity` and `{channel}_spend` per channel.
- Use `0` for inactive periods, not blank or NA.

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
| `File exceeds 50 MB limit` | CSV too large | Reduce file size or aggregate data |

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

BASE = "https://app.simba-mmm.com"
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
BASE="https://app.simba-mmm.com"

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

Set the key as the `SIMBA_API_KEY` environment variable in your MCP config.

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `SIMBA_API_URL` | Simba API base URL | `http://localhost:5005` |
| `SIMBA_API_KEY` | Your Simba API key | (required) |

## Transport Modes

The server supports all MCP transport modes:

```bash
# stdio (default) — for Cursor, Claude Code
simba-mcp

# Streamable HTTP — for remote deployment
simba-mcp --transport streamable-http --port 8100

# SSE — legacy transport
simba-mcp --transport sse --port 8100

# Or via uvicorn directly
uvicorn simba_mcp.server:app --host 0.0.0.0 --port 8100
```

## License

MIT
