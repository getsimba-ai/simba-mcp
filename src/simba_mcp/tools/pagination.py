"""Optional response bounding for legacy workflow endpoints without pagination."""


def page(payload: dict, key: str, limit: int | None, offset: int) -> dict:
    if limit is None and offset == 0:
        return payload
    if (limit is not None and not 1 <= limit <= 200) or offset < 0:
        return {
            "error": "limit must be 1-200 or null; offset must be nonnegative.",
            "_status_code": 400,
        }
    rows = payload.get(key)
    if not isinstance(rows, list) or payload.get("error"):
        return payload
    end = offset + (limit if limit is not None else 50)
    return {
        **payload,
        key: rows[offset:end],
        "_mcp_page": {
            "offset": offset,
            "returned": len(rows[offset:end]),
            "total": len(rows),
            "next_offset": end if end < len(rows) else None,
            "mode": "client_side",
            "stable_snapshot": False,
        },
    }
