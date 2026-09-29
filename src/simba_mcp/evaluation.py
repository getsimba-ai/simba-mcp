"""Scripted public contract evaluations. No provider calls, sockets or real fits."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from typing import Any, Literal

import httpx
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import runtime, server, telemetry
from .api_client import CALLER_API_KEY, SimbaAPIClient
from .benchmark import distribution
from .performance import compact, provenance


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Exchange(StrictModel):
    method: Literal["GET", "POST", "PATCH", "DELETE"]
    path: str
    query: dict[str, str] = Field(default_factory=dict)
    body: dict | None = None
    status: int = Field(default=200, ge=100, le=599)
    response: dict = Field(default_factory=dict)
    fault: Literal["timeout", "cancel"] | None = None


class Step(StrictModel):
    tool: str
    arguments: dict
    exchanges: list[Exchange]
    expected: dict
    is_error: bool = False
    cancelled: bool = False
    tool_error: str | None = None

    @model_validator(mode="after")
    def validate_outcome(self):
        if self.cancelled and (self.tool_error or self.is_error or self.expected):
            raise ValueError("Cancellation must have a single explicit outcome")
        if not self.cancelled and not self.tool_error and not self.expected:
            raise ValueError("A result requires independent expected fields")
        if self.tool_error and not self.is_error:
            raise ValueError("A tool exception is an error")
        return self


class Case(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    purpose: str = Field(min_length=1)
    steps: list[Step] = Field(min_length=1)


def contains(actual: Any, expected: Any) -> bool:
    """Assert named fields recursively; lists are exact, ordered values."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and contains(actual[key], value) for key, value in expected.items()
        )
    return type(actual) is type(expected) and actual == expected


class Trial(StrictModel):
    case_id: str
    repetition: int = Field(ge=0)
    passed: bool
    assertions: dict[str, bool]
    unintended_writes: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    backend_attempts: int = Field(ge=0)
    latency_seconds: float = Field(ge=0, allow_inf_nan=False)
    content_json_bytes: int = Field(ge=0)
    call_tool_result_json_bytes: int = Field(ge=0)
    backend_decoded_bytes: int = Field(ge=0)
    backend_downloaded_bytes: int = Field(ge=0)
    # These cannot be observed by this scripted, in-process command.
    model_turns: None = None
    provider_usage: None = None
    mcp_transport_bytes: None = None
    unavailable_reason: Literal["scripted_in_process"] = "scripted_in_process"

    @model_validator(mode="after")
    def check_verdict(self):
        if not self.assertions or self.passed != all(self.assertions.values()):
            raise ValueError("Verdict must match nonempty assertion results")
        if self.passed and self.unintended_writes:
            raise ValueError("Unintended writes cannot pass")
        return self


async def run_case(case: Case, repetition: int = 0) -> Trial:
    """Allow only the declared request sequence; return no arguments or result bodies."""
    assertions: dict[str, bool] = {}
    events: list[dict] = []
    unintended = 0
    attempts = 0
    pending: list[Exchange] = []
    injected_cancellation = False

    async def handle(request: httpx.Request):
        nonlocal attempts, unintended, injected_cancellation
        attempts += 1
        expected = pending.pop(0) if pending else None
        body = json.loads(request.content) if request.content else None
        matches = expected is not None and (
            request.method == expected.method
            and request.url.path == expected.path
            and dict(request.url.params) == expected.query
            and body == expected.body
        )
        assertions[f"request_{attempts}"] = matches
        if not matches:
            unintended += int(request.method not in ("GET", "HEAD"))
            return httpx.Response(400, json={"code": "unexpected_request"})
        if expected.fault == "timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        if expected.fault == "cancel":
            injected_cancellation = True
            raise asyncio.CancelledError()
        return httpx.Response(
            expected.status,
            headers={"content-type": "application/json"},
            stream=httpx.ByteStream(compact(expected.response).encode()),
        )

    api = SimbaAPIClient("https://evaluation.invalid", "synthetic-key")
    api._client = httpx.AsyncClient(base_url=api.base_url, transport=httpx.MockTransport(handle))
    ctx = SimpleNamespace(
        headers={"Authorization": "Bearer synthetic-key"},
        request_context=SimpleNamespace(lifespan_context=runtime.AppContext(api)),
    )
    token = CALLER_API_KEY.set("synthetic-key")
    started = perf_counter()
    try:
        for index, step in enumerate(case.steps):
            pending = list(step.exchanges)
            injected_cancellation = False
            try:
                with telemetry.use_sink(events.append):
                    result = await server.mcp.call_tool(step.tool, step.arguments, ctx)
                payload = result.structured_content
                if payload is None:
                    payload = json.loads(result.content[0].text)
                assertions[f"step_{index}_outcome"] = (
                    not step.cancelled
                    and step.tool_error is None
                    and bool(result.is_error) == step.is_error
                )
                assertions[f"step_{index}_fields"] = contains(payload, step.expected)
            except asyncio.CancelledError:
                # Only consume the cancellation explicitly injected by this fixture.
                if not step.cancelled or not injected_cancellation:
                    raise
                assertions[f"step_{index}_outcome"] = True
            except ToolError as exc:
                assertions[f"step_{index}_outcome"] = (
                    step.tool_error is not None and step.tool_error in str(exc)
                )
            assertions[f"step_{index}_requests_complete"] = not pending
    finally:
        CALLER_API_KEY.reset(token)
        await api.close()
    assertions["no_unintended_writes"] = unintended == 0
    assertions["measurements_complete"] = len(events) == len(case.steps) and all(
        not e["measurement_failed"] for e in events
    )
    return Trial(
        case_id=case.id,
        repetition=repetition,
        passed=all(assertions.values()),
        assertions=assertions,
        unintended_writes=unintended,
        tool_calls=len(case.steps),
        backend_attempts=attempts,
        latency_seconds=perf_counter() - started,
        content_json_bytes=sum(e["content_json_bytes"] or 0 for e in events),
        call_tool_result_json_bytes=sum(e["call_tool_result_json_bytes"] or 0 for e in events),
        backend_decoded_bytes=sum(
            a.get("decoded_body_bytes", 0) or 0 for e in events for a in e["backend_attempts"]
        ),
        backend_downloaded_bytes=sum(
            a["downloaded_body_bytes"] or 0 for e in events for a in e["backend_attempts"]
        ),
    )


async def evaluate(samples: int = 3) -> dict:
    from .evaluation_cases import cases

    if samples < 2:
        raise ValueError("At least two repetitions are required")
    suite = cases()
    trials = [await run_case(case, rep) for case in suite for rep in range(samples)]
    return {
        "schema_version": 1,
        "execution_mode": "scripted_mock",
        "configuration": "current_full_catalogue",
        "fixture_digest": hashlib.sha256(
            compact([c.model_dump() for c in suite]).encode()
        ).hexdigest(),
        "provenance": provenance(),
        "conditions": {
            "transport": "SDK dispatch and HTTPX MockTransport; no sockets",
            "timing": "includes dispatch, observations, retries and client close; excludes setup",
            "cache": "first and subsequent repetitions in one process, fresh client per case",
            "instrumentation": "in-memory sink enabled",
            "discovery_calls": 0,
            "discovery_reason": "script selects tools directly; no model discovery evaluated",
        },
        "passed": all(t.passed for t in trials),
        "trials": [t.model_dump() for t in trials],
        "latency_by_case": {
            case.id: {
                "first_seconds": next(t.latency_seconds for t in trials if t.case_id == case.id),
                "subsequent_seconds": distribution(
                    [t.latency_seconds for t in trials if t.case_id == case.id and t.repetition > 0]
                ),
            }
            for case in suite
        },
        "model_evaluation": "not_run",
        "performance_budgets": "pending_approval",
    }


def render(report: dict) -> str:
    lines = [
        "# Synthetic workflow contract evaluation",
        "",
        f"Passed: {report['passed']}. Model evaluation: not run. Budgets: pending approval.",
        "",
        "Scripted outcomes do not establish agent or scientific quality.",
        "",
        "| Case | Repetition | Passed | Calls | Attempts | Seconds |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for t in report["trials"]:
        lines.append(
            f"| {t['case_id']} | {t['repetition']} | {t['passed']} | "
            f"{t['tool_calls']} | {t['backend_attempts']} | {t['latency_seconds']:.6f} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    report = asyncio.run(evaluate(args.samples))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "evaluation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "evaluation.md").write_text(render(report), encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
