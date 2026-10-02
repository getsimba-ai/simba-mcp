# Executable synthetic examples

<!-- Generated from evaluation.role_workflows by guidance.coverage. -->

These examples execute through registered selected profiles with HTTPX MockTransport. Identifiers and outputs are synthetic, not live acceptance. Follow the declared prerequisites before using real objects. Refusals and uncertain writes never authorise a retry.

## role_campaign_mapping

Replace the explicitly authorised complete campaign map, then inspect the result.

Profiles: marketer, data_scientist, full.

Prerequisites: The user approves all replacement rows and exact channel keys.

Interpretation and recovery: Explicit user intent is required. PUT replaces the whole map; retain all authorised rows. A timeout leaves the write uncertain. Inspect facts, then hand off before another write.

Step 1:

```json
{
  "name": "set_campaign_mapping",
  "arguments": {
    "model_hash": "model-example",
    "rows": [
      {
        "platform": "meta",
        "campaign_id": "campaign-example",
        "channel": "search_clicks"
      }
    ]
  }
}
```

Expected observable fields:

```json
{
  "map": [
    {
      "platform": "meta",
      "campaign_id": "campaign-example",
      "channel": "search_clicks"
    }
  ],
  "conflicts": [],
  "drift": []
}
```

Step 2:

```json
{
  "name": "list_campaigns",
  "arguments": {
    "model_hash": "model-example"
  }
}
```

Expected observable fields:

```json
{
  "campaigns": [
    {
      "platform": "meta",
      "account_id": "account-example",
      "campaign_id": "campaign-example",
      "channel": "search_clicks",
      "status": "mapped"
    }
  ],
  "currency": "GBP",
  "window": {
    "start": "2026-09-01",
    "end": "2026-09-28"
  }
}
```

## role_mapping_uncertain

Inspect campaign facts after an uncertain mapping write; never replay automatically.

Profiles: marketer, data_scientist, full.

Prerequisites: One replacement was authorised; its transport fails.

Interpretation and recovery: Explicit user intent is required. PUT replaces the whole map; retain all authorised rows. A timeout leaves the write uncertain. Inspect facts, then hand off before another write.

Step 1:

```json
{
  "name": "set_campaign_mapping",
  "arguments": {
    "model_hash": "model-example",
    "rows": [
      {
        "platform": "meta",
        "campaign_id": "campaign-example",
        "channel": "search_clicks"
      }
    ]
  }
}
```

Expected observable fields:

```json
{
  "_status_code": 503
}
```

Step 2:

```json
{
  "name": "list_campaigns",
  "arguments": {
    "model_hash": "model-example"
  }
}
```

Expected observable fields:

```json
{
  "campaigns": [
    {
      "platform": "meta",
      "account_id": "account-example",
      "campaign_id": "campaign-example",
      "channel": "search_clicks",
      "status": "mapped"
    }
  ],
  "currency": "GBP",
  "window": {
    "start": "2026-09-01",
    "end": "2026-09-28"
  }
}
```
