"""Safe, actionable additions to legacy error dictionaries."""

from typing import Any


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
    result.setdefault("_error_code", code)
    result.setdefault("_next_action", action)
    return result
