# Executable synthetic examples

<!-- Generated from evaluation.role_workflows by guidance.coverage. -->

These examples execute through registered selected profiles with HTTPX MockTransport. Identifiers and outputs are synthetic, not live acceptance. Follow the declared prerequisites before using real objects. Refusals and uncertain writes never authorise a retry.

## role_experiment_priorities

Read experiment screening priorities and retain exclusions and uncertainty limits.

Profiles: marketer, reviewer, data_scientist, full.

Prerequisites: A saved model has posterior marginal evidence and the backend supports test-priorities.

Interpretation and recovery: Score is local binary perfect-information screening, not expected test benefit, design or recommended test budget.

Step 1:

```json
{
  "name": "recommend_incrementality_tests",
  "arguments": {
    "model_hash": "model-example",
    "budget": 1000.0,
    "limit": 3
  }
}
```

Expected observable fields:

```json
{
  "method": "normal_approximation",
  "budget": 1000.0,
  "items": [
    {
      "channel": "search_clicks",
      "score": 12.0,
      "design_hint": {
        "available": false
      }
    }
  ],
  "excluded": [
    {
      "channel": "tv_grps",
      "reason": "posterior_unavailable"
    }
  ]
}
```

## role_experiment_unsupported

Stop experiment screening when the backend endpoint is unsupported.

Profiles: marketer, reviewer, data_scientist, full.

Prerequisites: Saved model is known; no experiment creation is authorised.

Interpretation and recovery: A missing route is an unavailable capability. Preserve refusal and hand off; do not fit or fabricate a score.

Step 1:

```json
{
  "name": "recommend_incrementality_tests",
  "arguments": {
    "model_hash": "model-example"
  }
}
```

Expected observable fields:

```json
{
  "_status_code": 405
}
```
