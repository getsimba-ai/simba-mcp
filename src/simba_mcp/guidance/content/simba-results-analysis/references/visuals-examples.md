# Executable synthetic examples

<!-- Generated from evaluation.role_workflows by guidance.coverage. -->

These examples execute through registered selected profiles with HTTPX MockTransport. Identifiers and outputs are synthetic, not live acceptance. Follow the declared prerequisites before using real objects. Refusals and uncertain writes never authorise a retry.

## role_native_results

Read response curves and decomposition in a visual or JSON-only client.

Profiles: marketer, reviewer, data_scientist, full.

Prerequisites: Saved model is known. No capability/schema discovery is needed.

Interpretation and recovery: JSON remains authoritative. Missing points stay gaps; Overlap is a separate reconciliation term in KPI units.

Step 1:

```json
{
  "name": "show_response_curves",
  "arguments": {
    "model_hash": "model-example"
  }
}
```

Expected observable fields:

```json
{
  "response_curves": [
    {
      "Spend": 100,
      "search_clicks": null
    }
  ],
  "channel_map": {
    "search_clicks": "Search"
  }
}
```

Step 2:

```json
{
  "name": "show_decomposition",
  "arguments": {
    "model_hash": "model-example"
  }
}
```

Expected observable fields:

```json
{
  "contributions": [
    {
      "Date": "2026-09-01",
      "search_clicks": 10,
      "Overlap": -2
    }
  ],
  "model_config": {
    "attribution": "removal_lift"
  }
}
```
