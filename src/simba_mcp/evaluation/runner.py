"""Deterministic MCP dispatch against strict synthetic backend exchanges."""

from __future__ import annotations

import asyncio
import hashlib
import json
from time import perf_counter
from types import SimpleNamespace
from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

from .. import runtime, server, telemetry
from ..api_client import CALLER_API_KEY, SimbaAPIClient
from ..measurements import compact, distribution, provenance
from .contracts import Case, Exchange, Trial


def contains(actual: Any, expected: Any) -> bool:
    """Assert named fields recursively; lists are exact, ordered values."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and contains(actual[key], value) for key, value in expected.items()
        )
    return type(actual) is type(expected) and actual == expected


async def run_case(
    case: Case, repetition: int = 0, *, mcp_server=None, observe_result=None
) -> Trial:
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
                    result = await (mcp_server or server.mcp).call_tool(
                        step.tool, step.arguments, ctx
                    )
                payload = result.structured_content
                if payload is None:
                    payload = json.loads(result.content[0].text)
                if observe_result is not None:
                    observe_result(payload)
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


async def evaluate(samples: int = 3, description_mode: str = "legacy") -> dict:
    from .cases import cases

    if samples < 2:
        raise ValueError("At least two repetitions are required")
    suite = cases()
    instance = server.create_server(description_mode)
    trials = [
        await run_case(case, rep, mcp_server=instance) for case in suite for rep in range(samples)
    ]
    return {
        "schema_version": 1,
        "execution_mode": "scripted_mock",
        "configuration": "current_full_catalogue"
        if description_mode == "legacy"
        else "compact_descriptions",
        "description_mode": description_mode,
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


async def evaluate_roles(description_mode: str = "compact") -> dict:
    """Current deterministic role jobs; frozen provider cohorts are not modified."""
    from ..guidance import MANIFEST
    from ..profiles import PROFILES
    from .role_workflows import role_workflows

    workflows = role_workflows()
    trials = []
    for workflow in workflows:
        for role in workflow.roles:
            trial = await run_case(
                workflow.case,
                mcp_server=server.create_server(description_mode, profile=role),
            )
            trials.append({"profile": role, **trial.model_dump()})
    catalogue = await server.create_server(description_mode).list_tools()
    return {
        "schema_version": 1,
        "execution_mode": "scripted_mock",
        "workflow_version": 1,
        "guidance_version": MANIFEST["version"],
        "profile_counts": {
            "full": len(catalogue),
            "data_scientist": len(catalogue),
            **{role: len(names) for role, names in PROFILES.items()},
        },
        "description_mode": description_mode,
        "fixture_sha256": hashlib.sha256(
            compact([workflow.case.model_dump() for workflow in workflows]).encode()
        ).hexdigest(),
        "catalogue_sha256": hashlib.sha256(
            compact([tool.model_dump(mode="json") for tool in catalogue]).encode()
        ).hexdigest(),
        "provenance": provenance(),
        "passed": all(trial["passed"] for trial in trials),
        "trials": trials,
        "model_assisted": "NOT RUN: owned by issue #40; method and budget required",
        "named_clients": "NOT RUN: maintainer must declare supported release scope",
        "deployment": "NOT RUN: source/package candidate is separate from hosting",
        "historical_provider_reports": "unchanged; frozen 81/37/38 catalogue only",
    }
