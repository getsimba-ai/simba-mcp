# Executable synthetic examples

<!-- Generated from evaluation.role_workflows by guidance.coverage. -->

These examples execute through registered selected profiles with HTTPX MockTransport. Identifiers and outputs are synthetic, not live acceptance. Follow the declared prerequisites before using real objects. Refusals and uncertain writes never authorise a retry.

## study_review

Review saved Studies evidence without calling missing holdout evidence a pass.

Profiles: marketer, reviewer, data_scientist, full.

Prerequisites: Saved study and evaluations are known.

Interpretation and recovery: not_evaluated stays not_evaluated. A read may produce an access audit event.

Step 1:

```json
{
  "name": "list_study_evaluations",
  "arguments": {
    "run_id": "run-example",
    "expand": [
      "report"
    ]
  }
}
```

Expected observable fields:

```json
{
  "evaluations": [
    {
      "id": "evaluation-example",
      "report": {
        "checks": [
          {
            "metric": "holdout",
            "status": "not_evaluated",
            "basis": {
              "reason": "not_collected"
            }
          }
        ]
      }
    }
  ]
}
```
