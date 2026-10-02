# Executable synthetic examples

<!-- Generated from evaluation.role_workflows by guidance.coverage. -->

These examples execute through registered selected profiles with HTTPX MockTransport. Identifiers and outputs are synthetic, not live acceptance. Follow the declared prerequisites before using real objects. Refusals and uncertain writes never authorise a retry.

## role_campaign_facts

Inspect campaign spend beside platform-attributed and channel-derived incremental evidence.

Profiles: marketer, reviewer, data_scientist, full.

Prerequisites: Model and campaign-facts source exist; facts and attribution windows match.

Interpretation and recovery: Platform conversions are attributed facts. Campaign incremental ROAS inherits channel assumptions and is not independently measured.

Step 1:

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

Step 2:

```json
{
  "name": "get_campaign_report",
  "arguments": {
    "model_hash": "model-example",
    "start": "2026-09-01",
    "end": "2026-09-28",
    "group_by": "channel",
    "metrics": [
      "spend"
    ]
  }
}
```

Expected observable fields:

```json
{
  "rows": [
    {
      "group": "search_clicks",
      "metric": "spend",
      "value": 2800,
      "unit": "GBP"
    }
  ],
  "meta": {
    "basis": "campaign_facts"
  }
}
```

Step 3:

```json
{
  "name": "get_campaign_incrementality",
  "arguments": {
    "model_hash": "model-example",
    "start": "2026-09-01",
    "end": "2026-09-28"
  }
}
```

Expected observable fields:

```json
{
  "rows": [
    {
      "platform": "meta",
      "account_id": "account-example",
      "campaign_id": "campaign-example",
      "channel": "search_clicks",
      "status": "mapped",
      "incremental_roas": 2.0,
      "method": "channel_factor",
      "interval": "unavailable"
    }
  ]
}
```

## role_campaign_empty

Stop and hand off when campaign facts are unavailable.

Profiles: marketer, reviewer, data_scientist, full.

Prerequisites: A model is known; the app owns source registration.

Interpretation and recovery: Missing facts are not zero conversions. Do not create or run a pipeline.

Step 1:

```json
{
  "name": "get_campaign_report",
  "arguments": {
    "model_hash": "model-example"
  }
}
```

Expected observable fields:

```json
{
  "_status_code": 404
}
```
