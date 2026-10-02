"""Offline measurements of the actual local MCP HTTP surface (PERF-01)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from typing import Any

from .measurements import compact, provenance


def capture_surface(
    description_mode: str | None = None, *, preference_measurement: dict | None = None
) -> tuple[bytes, bytes]:
    """Exercise real HTTP middleware with an instance-local synthetic preference client."""
    from .oauth import oauth_enabled

    if oauth_enabled():
        raise ValueError("Offline surface capture requires MCP_OAUTH_ENABLED to be disabled.")

    from starlette.testclient import TestClient

    from . import runtime, server

    measurements = preference_measurement if preference_measurement is not None else {}
    measurements.update(requests=0, seconds=0.0, schema_version=1, profile="full", synthetic=True)

    class OfflinePreferenceClient:
        async def _request(self, method, path, **kwargs):
            if (
                method != "GET"
                or path != "/api/v1/mcp/preferences"
                or kwargs != {"retry_safe": False}
            ):
                raise RuntimeError(
                    "Offline surface capture permits only the synthetic preference exchange"
                )
            started = perf_counter()
            try:
                measurements["requests"] += 1
                return {"schema_version": 1, "profile": "full"}
            finally:
                measurements["seconds"] += perf_counter() - started

    @asynccontextmanager
    async def offline_lifespan(_server):
        yield runtime.AppContext(client=OfflinePreferenceClient(), serving_http=True)

    operator_profile = os.environ.get("SIMBA_TOOL_PROFILE", server.TOOL_PROFILE)
    measurements["operator_profile"] = operator_profile
    instance = server.create_server(
        description_mode or server.TOOL_DESCRIPTION_MODE, profile=operator_profile
    )
    # SDK v2 owns the per-instance low-level lifespan. Keep the actual profile
    # middleware and tool registrations; only its backend client is synthetic.
    instance._lowlevel_server.lifespan = offline_lifespan
    app = runtime.create_app(instance)
    with TestClient(app) as client:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer synthetic-surface-capture",
        }
        initial = client.post(
            "/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "simba-performance-report", "version": "1"},
                },
            },
        )
        initial.raise_for_status()
        listing = client.post(
            "/",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        listing.raise_for_status()
        return initial.content, listing.content


def surface_report(encoding: str = "none", description_mode: str | None = None) -> dict:

    counter = None
    if encoding != "none":
        try:
            import tiktoken
        except ImportError as exc:
            raise ValueError("Install simba-mcp[performance] to request tokenizer counts.") from exc
        counter = tiktoken.get_encoding(encoding)
    started = perf_counter()
    preference_measurement = {}
    initial_bytes, list_bytes = capture_surface(
        description_mode, preference_measurement=preference_measurement
    )
    from .server import TOOL_DESCRIPTION_MODE

    capture_seconds = perf_counter() - started
    initial, listing = json.loads(initial_bytes)["result"], json.loads(list_bytes)["result"]
    if listing.get("nextCursor"):
        raise ValueError("Catalogue is paginated; report would be incomplete.")

    def measure_text(text: str) -> dict:
        raw = text.encode("utf-8")
        return {
            "utf8_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "estimated_tokens": len(counter.encode(text, disallowed_special=()))
            if counter
            else None,
        }

    def measure(value: Any) -> dict:
        return measure_text(compact(value))

    tools = listing["tools"]
    return {
        "schema_version": 1,
        "description_mode": description_mode or TOOL_DESCRIPTION_MODE,
        "operator_profile": preference_measurement["operator_profile"],
        "provenance": provenance(),
        "capture": {
            "transport": "in_memory_http_json_response",
            "backend_requests": 0,
            "synthetic_preference_exchange": preference_measurement,
            "timing_boundary": "Capture seconds include local middleware and synthetic preference lookup. Preference seconds measure the local stub only, not hosted network latency. Tool telemetry begins after preference middleware and excludes that lookup.",
            "seconds": capture_seconds,
            "condition": "first app lifecycle in this process; imports and OS caches not controlled",
        },
        "tokenizer": {
            "encoding": encoding if counter else None,
            "status": "representation_estimate" if counter else "unavailable",
            "reason": "Encoded JSON is not host input or provider billing; independently encoded fields are not additive.",
        },
        "tool_count": len(tools),
        "tools_list_http_body": measure_text(list_bytes.decode("utf-8")),
        "tools_list_result": measure(listing),
        "initialize_http_body": measure_text(initial_bytes.decode("utf-8")),
        "server_instructions": measure(initial.get("instructions")),
        "tools": [
            {
                "name": tool["name"],
                "position": index,
                "total": measure(tool),
                "fields": {name: measure(value) for name, value in tool.items()},
            }
            for index, tool in enumerate(tools)
        ],
        "provider_usage": {
            "input_tokens": None,
            "cached_input_tokens": None,
            "output_tokens": None,
            "reason": "No model or host trial was run.",
        },
    }


def render_report(report: dict) -> str:
    rows = [
        "# MCP tool-surface baseline",
        "",
        "Local HTTP wire measurements. Token counts estimate this JSON representation only; they are not model usage or billing.",
        "",
        f"Operator profile: `{report['operator_profile']}`. Tools: **{report['tool_count']}**. Encoding: `{report['tokenizer']['encoding']}`.",
        f"Revision: `{report['provenance']['git_revision']}`; dirty: `{report['provenance']['git_dirty']}`.",
        f"Python: `{report['provenance']['python']}`. Packages: `{compact(report['provenance']['packages'])}`.",
        "",
        "| Representation | UTF-8 bytes | Estimated tokens |",
        "| --- | ---: | ---: |",
    ]
    for key in (
        "tools_list_http_body",
        "tools_list_result",
        "initialize_http_body",
        "server_instructions",
    ):
        item = report[key]
        rows.append(
            f"| {key} | {item['utf8_bytes']} | {item['estimated_tokens'] if item['estimated_tokens'] is not None else 'unavailable'} |"
        )
    rows += [
        "",
        "Field sizes below encode each field value independently. They do not include object keys or punctuation; token counts must not be summed.",
        "",
        "| Position | Tool / field | UTF-8 bytes | Estimated tokens |",
        "| ---: | --- | ---: | ---: |",
    ]
    for tool in report["tools"]:
        for name, item in [("total", tool["total"]), *tool["fields"].items()]:
            tokens = item["estimated_tokens"]
            rows.append(
                f"| {tool['position']} | {tool['name']} / {name} | {item['utf8_bytes']} | {tokens if tokens is not None else 'unavailable'} |"
            )
    rows += [
        "",
        "Real backend calls: zero. The real preference middleware performs an instance-local synthetic schema-1/full preference exchange. Provider usage: unavailable. HTTP headers, TLS and network compression are excluded.",
        "Capture timing includes the synthetic preference exchange, not a hosted lookup. Tool telemetry excludes preference middleware overhead; measure hosted lookup and end-to-end latency separately.",
        "",
    ]
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--encoding", choices=("none", "o200k_base", "cl100k_base"), default="none")
    parser.add_argument("--description-mode", choices=("legacy", "compact"), default="legacy")
    args = parser.parse_args(argv)
    report = surface_report(args.encoding, args.description_mode)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "surface.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "surface.md").write_text(render_report(report), encoding="utf-8")
    print(f"Wrote surface.json and surface.md to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
