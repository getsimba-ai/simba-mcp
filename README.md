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
