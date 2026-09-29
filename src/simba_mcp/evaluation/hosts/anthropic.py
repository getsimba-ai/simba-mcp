"""Anthropic Messages wire format for the shared bounded evaluation session."""

import json
from copy import deepcopy

import httpx

from .budget import Budget
from .models import MODEL, SONNET, model_configuration
from .session import run_session

# Preserve the existing adapter imports for archived run wrappers and callers.
__all__ = ["MODEL", "SONNET", "Budget", "client", "definitions", "model_configuration", "session"]

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


class Messages:
    endpoint = "https://api.anthropic.com/v1/messages"

    def request(self, history, tools, system, model):
        return {
            **model_configuration(model)["request"],
            "system": system,
            "tools": tools,
            "messages": history,
        }

    def consume(self, data, history):
        blocks = data["content"]
        history.append({"role": "assistant", "content": blocks})
        calls = [
            {"id": b["id"], "name": b["name"], "arguments": b["input"]}
            for b in blocks
            if b["type"] == "tool_use"
        ]
        return (
            calls,
            data.get("stop_reason", "unknown"),
            "".join(b.get("text", "") for b in blocks if b["type"] == "text"),
        )

    def append_results(self, history, replies):
        history.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": c["id"],
                        "content": json.dumps(payload),
                        "is_error": error,
                    }
                    for c, payload, error in replies
                ],
            }
        )


async def session(
    client, tools, prompt, dispatch, budget, checkpoint, *, max_turns=8, system_context=""
):
    return await run_session(
        client,
        tools,
        prompt,
        dispatch,
        budget,
        checkpoint,
        codec=Messages(),
        max_turns=max_turns,
        system_context=system_context,
    )


def client(api_key):
    """No automatic retries; key is never included in evidence records."""
    return httpx.AsyncClient(
        timeout=45, headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    )
