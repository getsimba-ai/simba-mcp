# Existing-data reporting and recovery

Marketer and reviewer now include `list_uploads`, `get_upload`, `get_data_schema`
and `get_data_report`. Full/data_scientist retain all tools. The upload listing includes
pipeline-ingested datasets, so no pipeline execution or upload permission is needed
to select an existing stored file. Pipeline administration remains full-only.

Use known dataset_id directly. Otherwise page `list_uploads` using offset and count;
get_upload gives exact columns/source identity. Inspect get_data_schema for declared
role vocabulary when needed. A schema role list does not declare the meaning of a
particular dataset's columns. Retain stored roles or explicit user declarations.

Call get_data_report with inclusive start/end, native/week/month/quarter, the requested
group_by/hierarchy/metrics and declared roles overrides. Exact schema conventions
recognise date, channel_spend and channel_activity. Unknown columns stay unknown and
unaggregated until declared. Do not silently guess units or KPI from the name.
Preserve dataset id/name/source/version/sha256/data_through and meta.aggregation.
Sum KPI/spend where declared; multiplier/control means and stock rules differ.
Weeks start Monday; weekly rows enter the month of their week-start date.

For report_too_large narrow dates or coarsen grain, retaining the requested meaning;
never silently truncate. A dataset_not_found or permission refusal remains explicit.
If missing role meaning changes the answer, stop for that declaration. No upload,
pipeline run or fit is needed to repair a read. Use section=workflow-examples.
