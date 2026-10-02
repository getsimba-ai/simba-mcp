# Executable synthetic examples

<!-- Generated from evaluation.role_workflows by guidance.coverage. -->

These examples execute through registered selected profiles with HTTPX MockTransport. Identifiers and outputs are synthetic, not live acceptance. Follow the declared prerequisites before using real objects. Refusals and uncertain writes never authorise a retry.

## role_campaign_budget

Inspect marginal evidence and calculate a bounded daily-equivalent campaign allocation.

Profiles: marketer, reviewer, data_scientist, full.

Prerequisites: Completed model, matching currency, facts and curves; an explicit daily channel total is supplied.

Interpretation and recovery: Read-only POST creates no run or platform change. Keep composite identity, provenance, constraints and unavailable uncertainty.

Step 1:

```json
{
  "name": "get_campaign_marginal_returns",
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
  "context_key": "basis-example",
  "currency": "GBP",
  "minor_digits": 2,
  "channels": [
    {
      "channel": "search_clicks",
      "status": "ready"
    }
  ],
  "rows": [
    {
      "platform": "meta",
      "account_id": "account-example",
      "campaign_id": "campaign-example",
      "channel": "search_clicks",
      "status": "mapped",
      "current_daily_spend": 100,
      "marginal_return": 1.4,
      "interval_status": "unavailable"
    }
  ],
  "provenance": {
    "curve_revision": "curve-example",
    "map_version": 3
  }
}
```

Step 2:

```json
{
  "name": "recommend_campaign_budgets",
  "arguments": {
    "model_hash": "model-example",
    "observation_window": {
      "start": "2026-09-01",
      "end": "2026-09-28"
    },
    "currency": "GBP",
    "channel_daily_budgets": {
      "search_clicks": 100
    },
    "expected_context_key": "basis-example"
  }
}
```

Expected observable fields:

```json
{
  "currency": "GBP",
  "channels": [
    {
      "channel": "search_clicks",
      "status": "ready",
      "total_daily_budget": 100,
      "rows": [
        {
          "platform": "meta",
          "account_id": "account-example",
          "campaign_id": "campaign-example",
          "channel": "search_clicks",
          "status": "mapped",
          "recommended_daily_budget": 100,
          "interval_status": "unavailable"
        }
      ]
    }
  ]
}
```

## role_budget_stale

Inspect fresh evidence after a stale campaign-budget basis refuses calculation.

Profiles: marketer, reviewer, data_scientist, full.

Prerequisites: The reviewed context key is supplied; facts change before calculation.

Interpretation and recovery: Do not relax constraints, retry the POST or apply budgets automatically.

Step 1:

```json
{
  "name": "get_campaign_marginal_returns",
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
  "context_key": "basis-example",
  "currency": "GBP",
  "minor_digits": 2,
  "channels": [
    {
      "channel": "search_clicks",
      "status": "ready"
    }
  ],
  "rows": [
    {
      "platform": "meta",
      "account_id": "account-example",
      "campaign_id": "campaign-example",
      "channel": "search_clicks",
      "status": "mapped",
      "current_daily_spend": 100,
      "marginal_return": 1.4,
      "interval_status": "unavailable"
    }
  ],
  "provenance": {
    "curve_revision": "curve-example",
    "map_version": 3
  }
}
```

Step 2:

```json
{
  "name": "recommend_campaign_budgets",
  "arguments": {
    "model_hash": "model-example",
    "observation_window": {
      "start": "2026-09-01",
      "end": "2026-09-28"
    },
    "currency": "GBP",
    "channel_daily_budgets": {
      "search_clicks": 100
    },
    "expected_context_key": "basis-example"
  }
}
```

Expected observable fields:

```json
{
  "_status_code": 409
}
```

Step 3:

```json
{
  "name": "get_campaign_marginal_returns",
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
  "context_key": "basis-new",
  "currency": "GBP",
  "minor_digits": 2,
  "channels": [
    {
      "channel": "search_clicks",
      "status": "ready"
    }
  ],
  "rows": [
    {
      "platform": "meta",
      "account_id": "account-example",
      "campaign_id": "campaign-example",
      "channel": "search_clicks",
      "status": "mapped",
      "current_daily_spend": 100,
      "marginal_return": 1.4,
      "interval_status": "unavailable"
    }
  ],
  "provenance": {
    "curve_revision": "curve-example",
    "map_version": 3
  }
}
```
