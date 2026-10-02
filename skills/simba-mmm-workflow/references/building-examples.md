# Executable synthetic examples

<!-- Generated from evaluation.role_workflows by guidance.coverage. -->

These examples execute through registered selected profiles with HTTPX MockTransport. Identifiers and outputs are synthetic, not live acceptance. Follow the declared prerequisites before using real objects. Refusals and uncertain writes never authorise a retry.

## create_mmm

Create one explicitly authorised synthetic MMM and inspect status.

Profiles: data_scientist, full.

Prerequisites: Dataset/schema prerequisites and user fit budget are supplied; fixture performs no real fit.

Interpretation and recovery: Marketer/reviewer must stop and reconnect with full before authoring. Pending status is not acceptance.

Step 1:

```json
{
  "name": "create_model",
  "arguments": {
    "uploaded_file_id": 1,
    "date_column": "week",
    "kpi_column": "units",
    "hierarchy_column": "brand",
    "channels": [
      {
        "name": "Search",
        "activity_column": "search_clicks",
        "spend_column": "search_spend"
      }
    ],
    "seasonality": true,
    "sampler": {
      "chains": 2,
      "tune": 100,
      "n_samples": 100
    }
  }
}
```

Expected observable fields:

```json
{
  "model_hash": "model-example",
  "status": "pending"
}
```

Step 2:

```json
{
  "name": "get_model_status",
  "arguments": {
    "model_hash": "model-example"
  }
}
```

Expected observable fields:

```json
{
  "model_hash": "model-example",
  "status": "complete"
}
```
