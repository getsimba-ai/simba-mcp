"""Versioned, packaged guidance shared by native Skills and the MCP fallback."""

import hashlib
import json
from importlib.resources import files

from simba_mcp.errors import api_error

MAX_RESPONSE_BYTES = 24_000
CONTENT = files(__package__).joinpath("content")
MANIFEST = json.loads(CONTENT.joinpath("manifest.json").read_text(encoding="utf-8"))


def read_guidance(topic: str = "index", section: str = "entrypoint") -> dict:
    """Resolve allowlisted identifiers only; return complete sections or an explicit refusal."""
    version = MANIFEST["version"]
    if topic == "index" and section == "entrypoint":
        result = {
            "guidance_version": version,
            "topics": [
                {
                    "topic": key,
                    "description": value["description"],
                    "sections": list(value["sections"]),
                }
                for key, value in MANIFEST["topics"].items()
            ],
        }
    else:
        entry = MANIFEST["topics"].get(topic)
        path = entry["sections"].get(section) if entry else None
        if path is None:
            return api_error(
                400,
                {
                    "code": "unknown_guidance",
                    "error": "Unknown guidance topic or section.",
                    "_next_action": "Request topic=index, then choose a listed topic and section.",
                },
            )
        # Neither user argument participates in a filesystem path.
        content = CONTENT.joinpath(path).read_text(encoding="utf-8")
        result = {
            "guidance_version": version,
            "topic": topic,
            "section": section,
            "sections": list(entry["sections"]),
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "content": content,
        }
    if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > MAX_RESPONSE_BYTES:
        return api_error(
            413,
            {
                "code": "guidance_too_large",
                "error": "Packaged guidance exceeds the response limit; no partial guidance returned.",
                "_next_action": "Use the native Skill and report the oversized section to the maintainer.",
            },
        )
    return result
