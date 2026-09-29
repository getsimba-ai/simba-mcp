"""Transport deadlines and bounded admission for the shared API client."""

import asyncio
import hashlib
import hmac
import json
import math
import secrets
import time
from collections import Counter
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx


class RequestDeadline(Exception):
    """The overall budget cannot accommodate another attempt."""


class RequestOverload(Exception):
    """The configured process or caller queue is full."""


@dataclass(frozen=True)
class RequestPolicy:
    """Values are operator-selected, not production recommendations."""

    total_seconds: float
    connect_seconds: float
    read_seconds: float
    write_seconds: float
    pool_seconds: float
    max_active: int
    max_active_per_caller: int
    max_queued: int
    max_queued_per_caller: int
    operation_seconds: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        for name in (
            "total_seconds",
            "connect_seconds",
            "read_seconds",
            "write_seconds",
            "pool_seconds",
        ):
            self._positive(name, getattr(self, name))
        for name in ("max_active", "max_active_per_caller", "max_queued", "max_queued_per_caller"):
            value = getattr(self, name)
            minimum = 0 if "queued" in name else 1
            if type(value) is not int or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
        if (
            self.max_active_per_caller > self.max_active
            or self.max_queued_per_caller > self.max_queued
        ):
            raise ValueError("Caller limits must not exceed process limits")
        if not isinstance(self.operation_seconds, dict) or set(self.operation_seconds) - {
            "read",
            "write",
            "upload",
        }:
            raise ValueError("operation_seconds supports read, write and upload only")
        for key, value in self.operation_seconds.items():
            self._positive(key, value)

    @staticmethod
    def _positive(name, value):
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")

    def seconds(self, method, path):
        operation = (
            "upload"
            if method.upper() == "POST" and path == "/api/v1/ingest"
            else "read"
            if method.upper() in {"GET", "HEAD"}
            else "write"
        )
        return self.operation_seconds.get(operation, self.total_seconds)

    def timeout(self, remaining):
        return httpx.Timeout(
            **{
                phase: min(getattr(self, f"{phase}_seconds"), remaining)
                for phase in ("connect", "read", "write", "pool")
            }
        )


def policy_from_json(raw):
    if not raw or not raw.strip():
        # Initial server defaults, configurable for each deployment's capacity.
        # Retain the previous 60-second HTTP phase limits.
        return RequestPolicy(
            total_seconds=180,
            connect_seconds=60,
            read_seconds=60,
            write_seconds=60,
            pool_seconds=60,
            max_active=32,
            max_active_per_caller=8,
            max_queued=128,
            max_queued_per_caller=32,
        )
    try:
        data = json.loads(raw)
        if data is False:
            return None
        if not isinstance(data, dict):
            raise TypeError("expected a JSON object")
        return RequestPolicy(**data)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid SIMBA_API_REQUEST_POLICY_JSON: {exc}") from exc


class RequestBudget:
    def __init__(self, seconds, *, clock=None):
        self.clock = clock or time.monotonic
        self.deadline = self.clock() + seconds

    def remaining(self):
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise RequestDeadline
        return remaining

    def retry(self, delay):
        # No attempt is started at or beyond the deadline. Its phase timeouts
        # are clipped to what remains; completion cannot be predicted in advance.
        if delay >= self.remaining():
            raise RequestDeadline


def retry_after_seconds(value, now=None):
    if not value:
        return None
    value = value.strip()
    if value.isdecimal():
        return float(value)
    try:
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            return None
        return max(0.0, (date - (now or datetime.now(UTC))).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


class RequestAdmission:
    """One shared-client queue; oldest eligible caller proceeds first.

    Queued calls do not hold active permits. Per-caller counters contain opaque
    keyed digests, are removed when unused, and are never emitted as telemetry.
    """

    def __init__(self, policy):
        self.policy = policy
        self.condition = asyncio.Condition()
        self.active = 0
        self.callers = Counter()
        self.waiters = []
        self.secret = secrets.token_bytes(32)

    def identity(self, credential):
        return hmac.new(self.secret, credential.encode(), hashlib.sha256).digest()

    def eligible(self, caller):
        return (
            self.active < self.policy.max_active
            and self.callers[caller] < self.policy.max_active_per_caller
        )

    @asynccontextmanager
    async def enter(self, caller):
        ticket = object()
        acquired = False
        async with self.condition:
            immediate = self.eligible(caller) and not any(
                self.eligible(key) for _, key in self.waiters
            )
            if not immediate:
                if (
                    len(self.waiters) >= self.policy.max_queued
                    or sum(key == caller for _, key in self.waiters)
                    >= self.policy.max_queued_per_caller
                ):
                    raise RequestOverload
                self.waiters.append((ticket, caller))
                try:
                    while True:
                        first = next(
                            (item for item in self.waiters if self.eligible(item[1])), None
                        )
                        if first is not None and first[0] is ticket:
                            break
                        await self.condition.wait()
                finally:
                    self.waiters.remove((ticket, caller))
                    self.condition.notify_all()
            self.active += 1
            self.callers[caller] += 1
            acquired = True
        try:
            yield
        finally:
            if acquired:
                async with self.condition:
                    self.active -= 1
                    self.callers[caller] -= 1
                    if not self.callers[caller]:
                        del self.callers[caller]
                    self.condition.notify_all()
