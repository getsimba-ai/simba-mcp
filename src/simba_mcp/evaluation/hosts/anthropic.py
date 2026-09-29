"""Bounded Messages API host example; dispatch and task grading are supplied separately."""

import json
import math
from copy import deepcopy
from dataclasses import dataclass
from time import perf_counter

import httpx

MODEL = "claude-haiku-4-5-20251001"
SEARCH = {"type": "tool_search_tool_bm25_20251119", "name": "tool_search_tool_bm25"}


def definitions(tools, mode):
    """Adapt SDK definitions without changing the MCP catalogue or copying its schemas."""
    if mode not in ("eager", "deferred"):
        raise ValueError("mode must be eager or deferred")
    result = []
    for tool in tools:
        item = {
            "name": tool.name,
            "description": tool.description,
            "input_schema": deepcopy(tool.input_schema),
        }
        if mode == "deferred":
            item["defer_loading"] = tool.name != "get_workflow_guidance"
        result.append(item)
    return [deepcopy(SEARCH), *result] if mode == "deferred" else result


@dataclass
class Budget:
    """One serial-run ledger. Unknown requests retain their preflight reservation."""

    cap: float
    prior: float = 0.0
    charged: float = 0.0
    reserved: float = 0.0

    def __post_init__(self):
        if any(not math.isfinite(x) or x < 0 for x in vars(self).values()):
            raise ValueError("Budget amounts must be finite and nonnegative")

    def reserve(self, request):
        bound = (2 * len(json.dumps(request).encode()) + 20000) / 1e6
        bound += request["max_tokens"] * 5 / 1e6
        if self.prior + self.charged + self.reserved + bound > self.cap:
            raise RuntimeError("Provider budget exhausted")
        self.reserved += bound
        return bound

    def settle(self, usage, reservation):
        names = ("input_tokens", "output_tokens")
        if any(type(usage.get(n)) is not int or usage[n] < 0 for n in names):
            raise ValueError("Missing provider usage; reservation retained")
        cache = [
            usage.get(n, 0) for n in ("cache_read_input_tokens", "cache_creation_input_tokens")
        ]
        if any(type(n) is not int or n < 0 for n in cache):
            raise ValueError("Invalid cache usage; reservation retained")
        cost = (usage["input_tokens"] + cache[0] + 2 * cache[1] + 5 * usage["output_tokens"]) / 1e6
        self.charged += cost
        self.reserved -= reservation
        if cost > reservation:
            raise RuntimeError("Provider usage exceeded reservation; stop")
        return cost


async def session(client, tools, prompt, dispatch, budget, checkpoint, *, max_turns=8):
    """No retries or automatic fallback. Only ordinary tool_use blocks are dispatched.

    checkpoint persists the serial budget before requests and after usage receipt.
    dispatch owns authorisation, schemas, errors and caller context; this adapter
    neither creates credentials nor interprets MCP annotation hints as permission.
    """
    messages = [{"role": "user", "content": prompt}]
    record = {"responses": [], "calls": [], "cost_usd": 0.0, "stop": "turn_limit"}
    started = perf_counter()
    for _ in range(max_turns):
        request = {
            "model": MODEL,
            "max_tokens": 1200,
            "temperature": 0,
            "system": "Complete only the authorised synthetic task. Preserve exact settings. "
            "Do not repeat already completed preflights. Missing evidence is not a pass. "
            "Never repeat an uncertain write. Return the requested facts as JSON.",
            "tools": tools,
            "messages": messages,
        }
        reservation = budget.reserve(request)
        checkpoint(record)
        response = await client.post("https://api.anthropic.com/v1/messages", json=request)
        if response.status_code != 200:
            record["stop"] = f"provider_http_{response.status_code}"
            checkpoint(record)
            raise RuntimeError(record["stop"] + "; no replay; use explicit eager fallback")
        data = response.json()
        record["cost_usd"] += budget.settle(data["usage"], reservation)
        record["responses"].append(data)
        checkpoint(record)
        blocks = data["content"]
        # Preserve server search results and references exactly for provider expansion.
        messages.append({"role": "assistant", "content": blocks})
        calls = [block for block in blocks if block["type"] == "tool_use"]
        replies = []
        for call in calls:
            payload, error = await dispatch(call["name"], call["input"])
            record["calls"].append(
                {"name": call["name"], "arguments": call["input"], "error": error}
            )
            replies.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call["id"],
                    "content": json.dumps(payload),
                    "is_error": error,
                }
            )
            checkpoint(record)
        if replies:
            messages.append({"role": "user", "content": replies})
        elif data.get("stop_reason") != "pause_turn":
            record["stop"] = data.get("stop_reason", "unknown")
            record["final_text"] = "".join(b.get("text", "") for b in blocks if b["type"] == "text")
            break
    record["seconds"] = perf_counter() - started
    checkpoint(record)
    return record


def client(api_key):
    """No automatic retries; key is never included in evidence records."""
    return httpx.AsyncClient(
        timeout=45, headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    )
