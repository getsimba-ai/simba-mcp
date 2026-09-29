"""One bounded provider loop, with provider wire formats supplied as codecs."""

import asyncio
import math
import sys
from time import perf_counter

SYSTEM = (
    "Complete only the authorised synthetic task. Preserve exact settings. "
    "Do not repeat already completed preflights. Missing evidence is not a pass. "
    "Never repeat an uncertain write. Return the requested facts as JSON."
)


async def run_session(
    client,
    tools,
    prompt,
    dispatch,
    budget,
    checkpoint,
    *,
    codec,
    max_turns=8,
    system_context="",
    session_timeout_seconds=180.0,
):
    """No retries or fallback; checkpoints precede requests and follow billed responses."""
    if not math.isfinite(session_timeout_seconds) or session_timeout_seconds <= 0:
        raise ValueError("session_timeout_seconds must be finite and positive")
    history = [{"role": "user", "content": prompt}]
    record = {
        "responses": [],
        "calls": [],
        "cost_usd": 0.0,
        "stop": "running",
        "session_timeout_seconds": session_timeout_seconds,
        "provider_seconds": 0.0,
        "dispatch_seconds": 0.0,
    }
    started = perf_counter()
    system = SYSTEM + ("\n\n" + system_context if system_context else "")

    def persist():
        active_error = sys.exception()
        try:
            checkpoint(record)
        except Exception as checkpoint_error:
            if active_error is None:
                raise
            active_error.add_note(f"Checkpoint failed: {type(checkpoint_error).__name__}")

    deadline = asyncio.timeout(session_timeout_seconds)
    try:
        async with deadline:
            for _ in range(max_turns):
                request = codec.request(history, tools, system, budget)
                reservation = budget.reserve(request)
                persist()
                provider_started = perf_counter()
                try:
                    response = await client.post(codec.endpoint, json=request)
                finally:
                    record["provider_seconds"] += perf_counter() - provider_started
                if response.status_code != 200:
                    record["stop"] = f"provider_http_{response.status_code}"
                    # Private checkpoint diagnostics only. Public evidence exporters must
                    # not copy provider bodies or headers containing account information.
                    record["provider_error"] = {
                        "status": response.status_code,
                        "retry_after": response.headers.get("retry-after"),
                        "body": response.text[:4096],
                    }
                    persist()
                    raise RuntimeError(record["stop"] + "; no replay or automatic fallback")
                data = response.json()
                record["responses"].append(data)
                charged_before = budget.charged
                try:
                    budget.settle(data["usage"], reservation)
                finally:
                    # Settlement can record a billed overrun and then stop. Persist that
                    # charge in both the shared ledger and this session before raising.
                    record["cost_usd"] += budget.charged - charged_before
                    persist()
                calls, stop, final_text = codec.consume(data, history)
                replies = []
                for call in calls:
                    attempt = {
                        "name": call["name"],
                        "arguments": call["arguments"],
                        "error": None,
                        "status": "started",
                    }
                    record["calls"].append(attempt)
                    persist()
                    dispatch_started = perf_counter()
                    try:
                        payload, error = await dispatch(call["name"], call["arguments"])
                        attempt.update(error=error, status="completed")
                    except BaseException as exc:
                        attempt.update(
                            error=True, status="interrupted", error_type=type(exc).__name__
                        )
                        raise
                    finally:
                        elapsed = perf_counter() - dispatch_started
                        attempt["seconds"] = elapsed
                        record["dispatch_seconds"] += elapsed
                    replies.append((call, payload, error))
                    persist()
                if replies:
                    codec.append_results(history, replies)
                elif stop != "pause_turn":
                    record["stop"] = stop
                    record["final_text"] = final_text
                    break
            else:
                record["stop"] = "turn_limit"
    except TimeoutError:
        record["stop"] = "session_timeout" if deadline.expired() else "operation_timeout"
        raise
    except asyncio.CancelledError:
        record["stop"] = "cancelled"
        raise
    except Exception as exc:
        if record["stop"] == "running":
            record["stop"] = "session_error"
        record["error_type"] = type(exc).__name__
        raise
    finally:
        record["seconds"] = perf_counter() - started
        persist()
    return record
