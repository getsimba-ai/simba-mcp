"""Additive error guidance without copying credentials or transport payloads."""

from typing import Any


def with_error_guidance(payload: dict[str, Any], *, retry_safe: bool) -> dict[str, Any]:
    """Preserve backend fields; classify errors without authorizing a retry."""
    status = payload.get("_status_code")
    if not isinstance(status, int) or status < 400:
        return payload
    codes = {
        400: "invalid_request",
        401: "authentication_required",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "invalid_request",
        429: "rate_limited",
    }
    transient = status in (429, 500, 502, 503, 504)
    action = {
        400: "Correct the request using the backend validation message.",
        401: "Provide your own Simba API key.",
        403: "Check this caller's project access and API key scopes.",
        404: "Check the object identifier and whether this backend supports the operation.",
        409: "Read the current object/revision before deciding whether to resubmit.",
        422: "Correct the request using the backend validation message.",
    }.get(
        status,
        "Retry the read later."
        if retry_safe
        else "Reconcile backend state before resubmitting. For study launches, reuse the same submission key and inputs.",
    )
    return {
        **payload,
        "_mcp_error": {
            "code": codes.get(status, "backend_error"),
            "transient": transient,
            "safe_to_retry": transient and retry_safe,
            "next_action": action,
        },
    }
