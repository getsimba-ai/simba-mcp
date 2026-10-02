After an uncertain launch reuse the exact submission key and inputs. Writes are
not automatically retried; inspect existing objects before repeating other writes.
On revision conflict reload and reconcile. Every refusal carries `_error_code` and
`_next_action`; `invalid_arguments` (422) means the arguments did not match the tool's
schema; fix the listed `fields` (a list, not a comma-separated string; an object, not a
JSON string) and call again. A new key can spend another attempt.
Quality evaluations use saved fitted-window evidence; missing diagnostics do not
pass and analyst acceptance remains in the frontend. Poll after cancellation until
the backend confirms the final state.
