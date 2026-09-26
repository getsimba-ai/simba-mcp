"""Safe, actionable additions to legacy error dictionaries."""

from typing import Any

# Backend workflow codes (jellyfish #824) and the recovery each one calls for. The backend
# sends `code` beside its unchanged human message; it wins over the status-derived guess.
NEXT_ACTIONS: dict[str, str] = {
    "engine_changed": "Validate and save a new recipe revision, then launch that revision.",
    "snapshot_not_executable": "Author a validated API recipe from the snapshot before launching.",
    "study_inactive": "The study is paused or archived; ask the owner to reactivate or pick another study.",
    "attempts_exhausted": "The attempt budget is used up; stop launching or ask the owner to raise max_attempts.",
    "concurrency_exhausted": "Wait for a running fit to finish, then retry with the same submission_key.",
    "stale_version": "Reload the object, reconcile your change, and resend with the current version.",
    "stale_evidence": "Re-run the pair assessment, then resolve against the new evidence hash.",
    "policy_not_found": "List the study's quality policies and pick one that belongs to it.",
    "policy_retired": "Choose the newest policy whose retired_at is null.",
    "provenance_missing": "Supply the source dataset or pipeline version again, or proceed without lineage claims.",
    "manual_signoff_requires_session": "Hand this step to the signed-in owner in the app; do not retry with an API key.",
    "submission_key_conflict": "Reuse a submission_key only with identical inputs; otherwise choose a new key.",
    # simba-mcp#26: raised by this server, not the backend, before the tool body runs.
    "invalid_arguments": (
        "Fix the listed fields to match the tool's input schema (e.g. pass a list, not a "
        "comma-separated string; an object, not a JSON string), then call again."
    ),
}


def api_error(status: int, payload: Any = None) -> dict:
    # Never expose HTML gateway bodies or transport exception strings.
    result = dict(payload) if isinstance(payload, dict) else {"error": "Backend request failed."}
    result.setdefault("error", "Backend request failed.")
    result["_status_code"] = status
    code, action = {
        400: ("invalid_request", "Check the input fields against backend schema/validation."),
        401: ("authentication_required", "Supply this caller's Simba API key."),
        402: (
            "entitlement_required",
            "Review the backend subscription or usage limit before proceeding.",
        ),
        405: (
            "unsupported_operation",
            "Check whether this backend supports the requested operation.",
        ),
        422: ("invalid_request", "Check the input fields against backend schema/validation."),
        403: ("permission_denied", "Check this caller's scopes and object access."),
        404: ("not_found", "Check the object ID and whether this backend supports the operation."),
        409: (
            "conflict",
            "Reload the object and inspect budget, state and evidence before proceeding.",
        ),
        412: (
            "revision_conflict",
            "Reload the latest revision and reconcile changes; do not blindly repeat.",
        ),
        413: (
            "payload_too_large",
            "Reduce upload size or request fewer result sections/channels or smaller pages; do not silently truncate evidence.",
        ),
        429: (
            "rate_limited",
            "Wait before another read; reconcile uncertain writes before repeating.",
        ),
    }.get(
        status,
        (
            "backend_unavailable",
            "Retry reads later. Reconcile writes; reuse the same study submission key and inputs.",
        ),
    )
    backend_code = result.get("code")
    if isinstance(backend_code, str) and backend_code:
        code, action = backend_code, NEXT_ACTIONS.get(backend_code, action)
    result.setdefault("_error_code", code)
    result.setdefault("_next_action", action)
    return result
