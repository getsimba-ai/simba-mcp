"""Advisory-tool dispatch through the real MCP handler and a qualified backend.

This owns evaluation instrumentation, not provider execution or another runner.
The configured backend owns OpenAI auth/admission. Only synthetic intent belongs
in this comparison; domain calls continue through the existing fixture dispatch.
"""

import asyncio
import math
import sys
from contextlib import asynccontextmanager
from time import perf_counter
from types import SimpleNamespace

from ...api_client import SimbaAPIClient
from ...errors import api_error
from ...guidance.routing import MODEL, VERSION, fallback, question, recommendation, validate_request
from ...runtime import AppContext
from ...tools.routing import recommend_workflow
from ...user_profiles import CURRENT_PROFILE
from ..experiments import fingerprint


class RoutingDispatch:
    def __init__(self, domain, client, budget, checkpoint, *, visible, input_rate, profile="full"):
        budget._decision_rate(input_rate)
        self.domain, self.budget, self.checkpoint = domain, budget, checkpoint
        self.visible, self.input_rate, self.profile = tuple(visible), input_rate, profile
        self.ctx = SimpleNamespace(
            request_context=SimpleNamespace(
                lifespan_context=AppContext(client, False, self.visible)
            )
        )
        self.routing_attempts = []

    def _persist(self):
        active = sys.exception()
        try:
            self.checkpoint(self.routing_attempts)
        except Exception as error:
            if active is None:
                raise
            active.add_note(f"Routing checkpoint failed: {type(error).__name__}")

    def __getattr__(self, name):
        # Existing graders continue to inspect domain execution/evidence only.
        return getattr(self.domain, name)

    async def __call__(self, name, arguments):
        if name != "recommend_workflow":
            return await self.domain(name, arguments)
        if name not in self.visible:
            return {"error": "Tool is outside this view."}, True
        if not isinstance(arguments, dict) or set(arguments) != {"request"}:
            return api_error(400, {"code": "invalid_routing_request"}), True
        try:
            validate_request(arguments["request"])
        except ValueError:
            return api_error(400, {"code": "invalid_routing_request"}), True
        reservation = self.budget.reserve_decision(
            {"model": MODEL, "input": arguments["request"], "questions": [question()]},
            input_rate=self.input_rate,
        )
        row = {
            "request_sha256": fingerprint(arguments),
            "routing_version": VERSION,
            "model": MODEL,
            "status": "reserved",
            "reservation_usd": reservation,
            "input_rate_usd_per_million": self.input_rate,
            "input_tokens": None,
            "cost_usd": None,
        }
        self.routing_attempts.append(row)
        # Durable checkpoint must succeed before submitting potentially paid HTTP.
        self._persist()
        token = CURRENT_PROFILE.set(self.profile)
        started = perf_counter()
        try:
            row["status"] = "submitted"
            self._persist()
            try:
                async with asyncio.timeout(3.25):
                    result = await recommend_workflow(arguments["request"], self.ctx)
            except TimeoutError:
                result = recommendation(fallback("provider_timeout"), self.visible)
            tokens = result.get("input_tokens")
            prepaid_refusal = result.get("_status_code") in (400, 401, 403, 413) or (
                result.get("reason") in ("disabled", "not_eligible", "limit_reached")
            )
            if prepaid_refusal:
                tokens = 0
            if tokens is not None:
                row["input_tokens"] = tokens
                row["cost_usd"] = tokens * self.input_rate / 1e6
                self.budget.settle_decision(
                    {"input_tokens": tokens}, reservation, input_rate=self.input_rate
                )
                row["status"] = "prepaid_refusal" if prepaid_refusal else "settled"
            else:
                row["status"] = "unknown_billing"
            row["result"] = result
            row["result_sha256"] = fingerprint(result)
            return result, bool(result.get("_status_code", 200) != 200)
        except BaseException as exc:
            row["status"] = "interrupted"
            row["error_type"] = type(exc).__name__
            raise
        finally:
            CURRENT_PROFILE.reset(token)
            row["seconds"] = perf_counter() - started
            self._persist()


@asynccontextmanager
async def routing_backend_client(url, credential):
    """Reuse the ordinary transport and ensure pool cleanup after a stopped run."""
    client = SimbaAPIClient(url, credential)
    try:
        yield client
    finally:
        await client.close()


def complete_task_usage(session, attempts):
    """Combine selector and main-agent work without changing archived session data."""
    routing = routing_usage(attempts)
    usage = [response.get("usage", {}) for response in session.get("responses", [])]
    main_known = (
        bool(usage)
        and session.get("stop") in ("end_turn", "max_tokens", "turn_limit")
        and type(session.get("cost_usd")) in (int, float)
        and math.isfinite(session["cost_usd"])
        and session["cost_usd"] >= 0
        and all(
            type(row.get("input_tokens")) is int
            and row["input_tokens"] >= 0
            and all(
                type(row.get(key, 0)) is int and row.get(key, 0) >= 0
                for key in ("cache_read_input_tokens", "cache_creation_input_tokens")
            )
            for row in usage
        )
    )
    return {
        "routing": routing,
        "total_input_tokens": (
            sum(
                row["input_tokens"]
                + row.get("cache_read_input_tokens", 0)
                + row.get("cache_creation_input_tokens", 0)
                for row in usage
            )
            + routing["input_tokens"]
            if main_known and routing["input_tokens"] is not None
            else None
        ),
        "total_cost_usd": (
            session["cost_usd"] + routing["cost_usd"]
            if main_known and routing["cost_usd"] is not None
            else None
        ),
        "seconds": session.get("seconds"),
        "accounting_complete": main_known and routing["unknown_billing_attempts"] == 0,
    }


def routing_usage(attempts):
    """Unknown charges/tokens are explicit, never counted as a zero-cost improvement."""
    unknown = sum(row.get("cost_usd") is None for row in attempts)
    return {
        "backend_attempts": len(attempts),
        "unknown_billing_attempts": unknown,
        "input_tokens": None if unknown else sum(row["input_tokens"] for row in attempts),
        "cost_usd": None if unknown else sum(row["cost_usd"] for row in attempts),
        "seconds": sum(row.get("seconds", 0) for row in attempts),
    }
