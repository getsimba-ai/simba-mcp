"""xAI Responses wire format; local MCP dispatch only, no provider-hosted tools."""

import json
from copy import deepcopy

import httpx

from .models import GROK, model_configuration
from .session import run_session


def definitions(tools, mode):
    if mode != "eager":
        raise ValueError("xAI evaluation supports eager tools only")
    return [
        {
            "type": "function",
            "name": t.name,
            "description": t.description,
            "parameters": deepcopy(t.input_schema),
        }
        for t in tools
    ]


class Responses:
    endpoint = "https://api.x.ai/v1/responses"

    def request(self, history, tools, system, budget):
        if budget.model != GROK:
            raise ValueError("xAI adapter requires its explicitly configured model")
        return {
            **model_configuration(budget.model, budget.reasoning_effort)["request"],
            "instructions": system,
            "tools": tools,
            "input": history,
        }

    def consume(self, data, history):
        if data.get("model") != GROK:
            raise ValueError("Provider returned an unexpected model; no fallback")
        status = data.get("status")
        if status not in ("completed", "incomplete") or data.get("error"):
            raise ValueError("Provider response did not complete; no replay")
        output = data["output"]
        if any(
            item.get("type") not in ("message", "reasoning", "function_call") for item in output
        ):
            raise ValueError("Unexpected provider-hosted output; no dispatch")
        # Preserve opaque reasoning and function calls exactly, never publish them.
        history.extend(deepcopy(output))
        calls = []
        for item in output:
            if item["type"] == "function_call":
                arguments = json.loads(item["arguments"])
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be an object")
                calls.append({"id": item["call_id"], "name": item["name"], "arguments": arguments})
        if status == "incomplete" and calls:
            raise ValueError("Incomplete provider tool request; no dispatch")
        text = "".join(
            block.get("text", "")
            for item in output
            if item["type"] == "message"
            for block in item.get("content", [])
            if block.get("type") == "output_text"
        )
        stop = "end_turn" if status == "completed" else "max_tokens"
        return calls, stop, text

    def append_results(self, history, replies):
        history.extend(
            {
                "type": "function_call_output",
                "call_id": call["id"],
                "output": json.dumps({"error": payload} if error else payload),
            }
            for call, payload, error in replies
        )


async def session(
    client,
    tools,
    prompt,
    dispatch,
    budget,
    checkpoint,
    *,
    max_turns=8,
    system_context="",
    session_timeout_seconds=180.0,
):
    return await run_session(
        client,
        tools,
        prompt,
        dispatch,
        budget,
        checkpoint,
        codec=Responses(),
        max_turns=max_turns,
        system_context=system_context,
        session_timeout_seconds=session_timeout_seconds,
    )


def client(api_key):
    """Read the key from the caller; never persist it or retry a request."""
    return httpx.AsyncClient(timeout=45, headers={"Authorization": "Bearer " + api_key})
