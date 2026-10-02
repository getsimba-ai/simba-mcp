# Executable synthetic examples

<!-- Generated from evaluation.role_workflows by guidance.coverage. -->

These examples execute through registered selected profiles with HTTPX MockTransport. Identifiers and outputs are synthetic, not live acceptance. Follow the declared prerequisites before using real objects. Refusals and uncertain writes never authorise a retry.

## role_saved_allocation

Compare two exact saved optimiser allocations without creating a new run.

Profiles: marketer, reviewer, data_scientist, full.

Prerequisites: Two owned saved run IDs are supplied for the same model.

Interpretation and recovery: Decision Revenue/ROI and OptimizedEvalRevenue/ROI remain separate; read-only views create no allocation.

Step 1:

```json
{
  "name": "show_optimizer_allocation",
  "arguments": {
    "model_hash": "model-example",
    "run_id": "optim-one"
  }
}
```

Expected observable fields:

```json
{
  "run_id": "optim-one",
  "model_hash": "model-example",
  "status": "complete",
  "results": [
    {
      "Channel": "search_clicks",
      "Spend": 100,
      "Revenue": 200,
      "ROI": 2.0,
      "OptimizedEvalRevenue": 300,
      "OptimizedEvalROI": 3.0
    }
  ]
}
```

Step 2:

```json
{
  "name": "show_optimizer_allocation",
  "arguments": {
    "model_hash": "model-example",
    "run_id": "optim-two"
  }
}
```

Expected observable fields:

```json
{
  "run_id": "optim-two",
  "model_hash": "model-example",
  "status": "complete",
  "results": [
    {
      "Channel": "search_clicks",
      "Spend": 120,
      "Revenue": 240,
      "ROI": 2.0,
      "OptimizedEvalRevenue": 360,
      "OptimizedEvalROI": 3.0
    }
  ]
}
```
