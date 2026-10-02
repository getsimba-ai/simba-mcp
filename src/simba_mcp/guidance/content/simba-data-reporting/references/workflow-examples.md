# Executable synthetic examples

<!-- Generated from evaluation.role_workflows by guidance.coverage. -->

These examples execute through registered selected profiles with HTTPX MockTransport. Identifiers and outputs are synthetic, not live acceptance. Follow the declared prerequisites before using real objects. Refusals and uncertain writes never authorise a retry.

## role_actual_data

Find an existing dataset and report September actual KPI and spend.

Profiles: marketer, reviewer, data_scientist, full.

Prerequisites: An owned dataset exists; the user declares units as KPI. No upload or pipeline refresh.

Interpretation and recovery: Preserve dataset identity, declared roles, units and aggregation. Actual totals are not model attribution.

Step 1:

```json
{
  "name": "list_uploads",
  "arguments": {
    "limit": 10
  }
}
```

Expected observable fields:

```json
{
  "files": [
    {
      "id": 7,
      "filename": "synthetic.csv"
    }
  ],
  "count": 1
}
```

Step 2:

```json
{
  "name": "get_upload",
  "arguments": {
    "file_id": 7
  }
}
```

Expected observable fields:

```json
{
  "id": 7,
  "filename": "synthetic.csv",
  "source_type": "pipeline",
  "columns": [
    {
      "name": "date",
      "dtype": "date"
    },
    {
      "name": "units",
      "dtype": "number"
    },
    {
      "name": "search_spend",
      "dtype": "number"
    }
  ]
}
```

Step 3:

```json
{
  "name": "get_data_schema",
  "arguments": {}
}
```

Expected observable fields:

```json
{
  "x-simba-roles": {
    "kpi": {
      "aggregation": "sum"
    }
  }
}
```

Step 4:

```json
{
  "name": "get_data_report",
  "arguments": {
    "dataset_id": 7,
    "start": "2026-09-01",
    "end": "2026-09-30",
    "granularity": "month",
    "metrics": [
      "kpi",
      "spend"
    ],
    "roles": {
      "units": "kpi"
    }
  }
}
```

Expected observable fields:

```json
{
  "dataset": {
    "id": 7,
    "source": "pipeline",
    "sha256": "synthetic-digest"
  },
  "granularity": "month",
  "rows": [
    {
      "period_start": "2026-09-01",
      "period_end": "2026-09-30",
      "group": "all",
      "metric": "kpi",
      "value": 400,
      "unit": "units"
    },
    {
      "period_start": "2026-09-01",
      "period_end": "2026-09-30",
      "group": "all",
      "metric": "spend",
      "value": 1200,
      "unit": "GBP"
    }
  ],
  "meta": {
    "basis": "dataset",
    "aggregation": {
      "kpi": "sum",
      "spend": "sum"
    }
  }
}
```

## role_report_recovery

Recover an oversized report by narrowing it, without changing the data.

Profiles: marketer, reviewer, data_scientist, full.

Prerequisites: Dataset 7 is known; declared roles are retained.

Interpretation and recovery: Do not truncate results or upload, refresh or fit to repair a reporting refusal.

Step 1:

```json
{
  "name": "get_data_report",
  "arguments": {
    "dataset_id": 7
  }
}
```

Expected observable fields:

```json
{
  "_status_code": 413
}
```

Step 2:

```json
{
  "name": "get_data_report",
  "arguments": {
    "dataset_id": 7,
    "start": "2026-09-01",
    "end": "2026-09-30",
    "granularity": "month",
    "metrics": [
      "kpi",
      "spend"
    ],
    "roles": {
      "units": "kpi"
    }
  }
}
```

Expected observable fields:

```json
{
  "dataset": {
    "id": 7,
    "source": "pipeline",
    "sha256": "synthetic-digest"
  },
  "granularity": "month",
  "rows": [
    {
      "period_start": "2026-09-01",
      "period_end": "2026-09-30",
      "group": "all",
      "metric": "kpi",
      "value": 400,
      "unit": "units"
    },
    {
      "period_start": "2026-09-01",
      "period_end": "2026-09-30",
      "group": "all",
      "metric": "spend",
      "value": 1200,
      "unit": "GBP"
    }
  ],
  "meta": {
    "basis": "dataset",
    "aggregation": {
      "kpi": "sum",
      "spend": "sum"
    }
  }
}
```
