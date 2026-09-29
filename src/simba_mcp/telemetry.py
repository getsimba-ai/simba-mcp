"""Opt-in numeric observations. No request arguments, identifiers or bodies are exported."""

from __future__ import annotations

import asyncio
import contextvars
import json
import os
import re
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from time import perf_counter

import httpx

# Explicit fixed labels only. Unknown routes collapse to "other". Placeholder values
# are matched and discarded, never copied into an observation.
ROUTES = (
    "/ingest/schema",
    "/ingest",
    "/ingest/{id}",
    "/datasets/{id}/report",
    "/models",
    "/models/{id}",
    "/models/{id}/status",
    "/models/{id}/results",
    "/models/{id}/link_var",
    "/models/{id}/contribution-groups",
    "/models/{id}/save",
    "/models/{id}/unsave",
    "/models/{id}/optimize",
    "/models/{id}/scenario",
    "/models/{id}/scenario/template",
    "/models/{id}/optimize/runs",
    "/models/{id}/scenario/runs",
    "/models/{id}/optimize/runs/{id}",
    "/models/{id}/scenario/runs/{id}",
    "/models/{id}/optimize/runs/{id}/pin",
    "/models/{id}/scenario/runs/{id}/pin",
    "/projects",
    "/projects/{id}",
    "/projects/{id}/studies",
    "/studies/{id}",
    "/studies/{id}/launch-eligibility",
    "/studies/{id}/overview",
    "/studies/{id}/runs",
    "/studies/{id}/recipes",
    "/studies/{id}/recipe-drafts",
    "/studies/{id}/quality-policies",
    "/studies/{id}/quality-policies/{id}",
    "/studies/{id}/quality-policies/{id}/diff/{id}",
    "/studies/{id}/evaluations",
    "/studies/{id}/decisions",
    "/studies/{id}/comparisons",
    "/studies/{id}/champion",
    "/studies/{id}/validation-pairs",
    "/studies/{id}/validation-resolutions",
    "/studies/{id}/adoptions",
    "/study-runs/{id}",
    "/study-runs/{id}/cancel",
    "/study-runs/{id}/evaluations",
    "/study-runs/{id}/prediction-access",
    "/study-runs/{id}/holdout-use",
    "/recipes/{id}/revisions",
    "/recipes/{id}/revisions/{id}",
    "/recipes/{id}/revisions/{id}/refreeze",
    "/recipes/{id}/revisions/{id}/diff/{id}",
    "/recipes/{id}/revisions/{id}/authoring",
    "/recipe-drafts/{id}",
    "/recipe-drafts/{id}/publish",
    "/recipe-draft-template",
    "/recipe-validation",
    "/pipelines",
    "/pipelines/{id}/versions",
    "/pipelines/{id}/runs",
    "/pipelines/{id}/runs/{id}",
    "/pipelines/{id}/schedule",
    "/projects/{id}/incrementality-tests",
    "/incrementality-tests/{id}",
    "/incrementality-tests/{id}/calibration",
    "/projects/{id}/incrementality-tests/import",
)
_ROUTES = tuple(
    (
        "/api/v1" + route,
        re.compile(re.escape("/api/v1" + route).replace(re.escape("{id}"), r"[^/?#]+") + r"\Z"),
    )
    for route in sorted(ROUTES, key=lambda x: (x.count("{id}"), x))
)
_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"})
_PHASES = frozenset({"http_parse", "result_filter", "result_cap_serialisation"})
MAX_ATTEMPT_DETAILS = 32
Sink = Callable[[dict], None]
_sink_override: contextvars.ContextVar[tuple[Sink | None] | None] = contextvars.ContextVar(
    "simba_metrics_sink", default=None
)
_observation: contextvars.ContextVar[Observation | None] = contextvars.ContextVar(
    "simba_metrics_observation", default=None
)


def route_label(path: str) -> str:
    path = path.split("?", 1)[0].split("#", 1)[0]
    for template, pattern in _ROUTES:
        if pattern.fullmatch(path):
            return template
    return "other"


def stderr_sink(event: dict) -> None:
    print(json.dumps(event, separators=(",", ":")), file=sys.stderr)


def get_sink() -> Sink | None:
    override = _sink_override.get()
    if override is not None:
        return override[0]
    return stderr_sink if os.environ.get("SIMBA_MCP_METRICS") == "stderr" else None


@contextmanager
def use_sink(sink: Sink | None) -> Iterator[None]:
    """Task-local override for an embedding application or synthetic benchmark."""
    token = _sink_override.set((sink,))
    try:
        yield
    finally:
        _sink_override.reset(token)


class Observation:
    def __init__(self, tool: str):
        self.started = perf_counter()
        self.event = {
            "schema_version": 1,
            "event": "simba_tool_metrics",
            "tool": tool,
            "outcome": "error",
            "duration_seconds": None,
            "backend_attempt_count": 0,
            "backend_attempts": [],
            "dropped_attempt_details": 0,
            "phase_seconds": {key: 0.0 for key in sorted(_PHASES)},
            "content_json_bytes": None,
            "call_tool_result_json_bytes": None,
            "measurement_serialisation_seconds": 0.0,
            "measurement_failed": False,
            "mcp_transport_bytes": None,
            "provider_usage": None,
        }

    def result(self, result) -> None:
        self.event["duration_seconds"] = perf_counter() - self.started
        self.event["outcome"] = "refused" if getattr(result, "is_error", False) else "ok"
        started = perf_counter()
        try:
            # These are representations, not claims about framing/compression on a transport.
            full = result.model_dump_json(by_alias=True, exclude_none=True)
            self.event["call_tool_result_json_bytes"] = len(full.encode("utf-8"))
            content = [
                block.model_dump(mode="json", by_alias=True, exclude_none=True)
                for block in result.content
            ]
            self.event["content_json_bytes"] = len(
                json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            )
        except Exception:  # noqa: BLE001 - observers cannot fail an otherwise valid tool call
            # Failure to measure must never become a tool failure or log its payload.
            self.event["measurement_failed"] = True
        finally:
            self.event["measurement_serialisation_seconds"] = perf_counter() - started


@contextmanager
def observe(tool: str, sink: Sink) -> Iterator[Observation]:
    observation = Observation(tool)
    token = _observation.set(observation)
    try:
        yield observation
    except asyncio.CancelledError:
        observation.event["outcome"] = "cancelled"
        raise
    finally:
        if observation.event["duration_seconds"] is None:
            observation.event["duration_seconds"] = perf_counter() - observation.started
        _observation.reset(token)
        try:
            sink(observation.event)
        except Exception:  # noqa: BLE001, S110 - never expose sink exception text or fail the tool
            pass


@contextmanager
def phase(name: str) -> Iterator[None]:
    observation = _observation.get()
    if observation is None or name not in _PHASES:
        yield
        return
    started = perf_counter()
    try:
        yield
    finally:
        observation.event["phase_seconds"][name] += perf_counter() - started


class Attempt:
    def __init__(self, method: str, path: str):
        self.event = {
            "method": method if method in _METHODS else "other",
            "route": route_label(path),
            "outcome": "error",
            "status_class": None,
            "duration_seconds": None,
            "downloaded_body_bytes": None,
            "decoded_body_bytes": None,
        }

    def response(self, response: httpx.Response) -> None:
        status = response.status_code // 100
        self.event["status_class"] = f"{status}xx" if status in range(1, 6) else "other"
        self.event["outcome"] = "http_error" if response.status_code >= 400 else "ok"
        try:
            decoded = len(response.content)
            downloaded = response.num_bytes_downloaded
            self.event["decoded_body_bytes"] = decoded
            # MockTransport prebuffered bodies can report zero downloaded bytes despite content.
            self.event["downloaded_body_bytes"] = downloaded if downloaded or not decoded else None
        except (httpx.ResponseNotRead, AttributeError):
            pass


@contextmanager
def backend_attempt(method: str, path: str) -> Iterator[Attempt | None]:
    observation = _observation.get()
    if observation is None:
        yield None
        return
    attempt = Attempt(method, path)
    observation.event["backend_attempt_count"] += 1
    started = perf_counter()
    try:
        yield attempt
    except asyncio.CancelledError:
        attempt.event["outcome"] = "cancelled"
        raise
    except httpx.TransportError:
        attempt.event["outcome"] = "transport_error"
        raise
    finally:
        attempt.event["duration_seconds"] = perf_counter() - started
        events = observation.event["backend_attempts"]
        if len(events) < MAX_ATTEMPT_DETAILS:
            events.append(attempt.event)
        else:
            observation.event["dropped_attempt_details"] += 1
