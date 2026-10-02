"""Synthetic, socket-free measurement overhead baseline. No fits or provider calls."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import tempfile
from contextlib import redirect_stderr
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import httpx

from . import runtime, server, telemetry
from .api_client import CALLER_API_KEY, SimbaAPIClient
from .measurements import compact, distribution, provenance

FIXTURE_VERSION = 1


def fixtures() -> list[dict]:
    """Deterministic public synthetic data, regenerated identically for each run."""
    curves = [
        {"Spend": row * 10, **{f"channel_{col}_activity": row * col / 10 for col in range(12)}}
        for row in range(100)
    ]
    results = {
        "response_curves": curves,
        "channel_summary": [
            {
                "Channel": f"channel_{col}_activity",
                "Revenue": 1000 + col,
                "Spend": 200,
                "ROI": (1000 + col) / 200,
            }
            for col in range(12)
        ],
        "contributions": [
            {
                "Date": row * 86400000,
                "Base": 10,
                **{f"channel_{col}_activity": row * col / 10 for col in range(12)},
            }
            for row in range(1000)
        ],
    }
    return [
        {
            "id": "small_status",
            "tool": "get_model_status",
            "arguments": {"model_hash": "synthetic"},
            "response": {"status": "completed", "progress": 100},
        },
        {
            "id": "large_results",
            "tool": "get_model_results",
            "arguments": {"model_hash": "synthetic"},
            "response": results,
        },
        {
            "id": "filtered_results",
            "tool": "get_model_results",
            "arguments": {
                "model_hash": "synthetic",
                "channels": ["channel_1_activity"],
                "max_grid_points": 20,
                "max_response_bytes": 1000000,
            },
            "response": results,
        },
    ]


async def benchmark(samples: int = 30) -> dict:
    if samples < 2:
        raise ValueError("At least two warm samples are required.")
    cases = fixtures()
    report = {
        "schema_version": 1,
        "fixture_version": FIXTURE_VERSION,
        "fixture_sha256": hashlib.sha256(compact(cases).encode()).hexdigest(),
        "provenance": provenance(),
        "conditions": {
            "httpx_log_level": logging.getLogger("httpx").getEffectiveLevel(),
            "transport": "SDK call_tool with HTTPX MockTransport; no sockets",
            "first_iteration": "first per mode/case in a shared process; fixture/client construction excluded",
            "warm": "same client and fixture, interleaved modes; reverse order on alternate rounds",
            "sink": "collect retains events in memory; stderr writes to a buffered temporary local file",
            "limits": "No network, TLS, model, production backend, OS cache control or host latency measured. Ratios describe local overhead only.",
        },
        "cases": [],
        "provider_usage": None,
    }
    key_token = CALLER_API_KEY.set("synthetic-benchmark-key")
    try:
        for case in cases:
            raw = compact(case["response"]).encode("utf-8")

            def handle(request, body=raw):
                return httpx.Response(
                    200, headers={"content-type": "application/json"}, stream=httpx.ByteStream(body)
                )

            api = SimbaAPIClient("https://synthetic.invalid", "synthetic-benchmark-key")
            api._client = httpx.AsyncClient(
                base_url=api.base_url, transport=httpx.MockTransport(handle)
            )
            ctx = SimpleNamespace(
                headers={"Authorization": "Bearer synthetic-benchmark-key"},
                request_context=SimpleNamespace(lifespan_context=runtime.AppContext(api)),
            )
            events = []
            modes = {"disabled": None, "collect": events.append, "stderr": telemetry.stderr_sink}
            durations = {name: [] for name in modes}
            expected = None
            try:
                with (
                    tempfile.TemporaryFile(mode="w+", encoding="utf-8") as sink_file,
                    redirect_stderr(sink_file),
                ):
                    for index in range(samples + 1):
                        order = list(modes) if index % 2 == 0 else list(reversed(modes))
                        for name in order:
                            with telemetry.use_sink(modes[name]):
                                start = perf_counter()
                                result = await server.mcp.call_tool(
                                    case["tool"], case["arguments"], ctx
                                )
                                durations[name].append(perf_counter() - start)
                            wire = result.model_dump_json(by_alias=True, exclude_none=True)
                            if result.is_error:
                                raise RuntimeError(
                                    "Synthetic benchmark unexpectedly refused a fixture."
                                )
                            if expected is None:
                                expected = wire
                            elif wire != expected:
                                raise RuntimeError("Instrumentation changed a synthetic result.")
                measurements = {
                    name: {
                        "first_iteration_seconds": times[0],
                        "warm_seconds": distribution(times[1:]),
                    }
                    for name, times in durations.items()
                }
                baseline = measurements["disabled"]["warm_seconds"]["median"]
                for mode in measurements.values():
                    median = mode["warm_seconds"]["median"]
                    mode["median_difference_from_disabled_seconds"] = median - baseline
                    mode["median_ratio_to_disabled"] = median / baseline if baseline else None
                report["cases"].append(
                    {
                        "id": case["id"],
                        "fixture_body_bytes": len(raw),
                        "unchanged_result": True,
                        "measurements": measurements,
                        "example_observation": events[-1],
                    }
                )
            finally:
                await api.close()
    finally:
        CALLER_API_KEY.reset(key_token)
    return report


def render(report: dict) -> str:
    rows = [
        "# Synthetic instrumentation overhead",
        "",
        "No live backend, model calls or production fits. These are local measurements, not a performance acceptance budget.",
        "",
        f"Fixture version: {report['fixture_version']}; SHA-256: `{report['fixture_sha256']}`.",
        f"Revision: `{report['provenance']['git_revision']}`; dirty: `{report['provenance']['git_dirty']}`.",
        "",
        "First iteration is first per case/mode in one process. Warm samples use the same client and alternate mode order.",
        "The stderr sink writes a buffered temporary local file; a real log consumer may have different overhead.",
        "",
        "| Case | Mode | First ms | Warm samples | Median ms | P95 ms | Median ratio to disabled |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in report["cases"]:
        for name, measurement in case["measurements"].items():
            warm = measurement["warm_seconds"]
            rows.append(
                f"| {case['id']} | {name} | {1000 * measurement['first_iteration_seconds']:.3f} | {warm['samples']} | {1000 * warm['median']:.3f} | {1000 * warm['p95']:.3f} | {measurement['median_ratio_to_disabled']:.3f} |"
            )
    return "\n".join(rows) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=30)
    args = parser.parse_args(argv)
    if args.samples < 2:
        parser.error("--samples must be at least 2")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    report = asyncio.run(benchmark(args.samples))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "overhead.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "overhead.md").write_text(render(report), encoding="utf-8")
    print(f"Wrote overhead.json and overhead.md to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
