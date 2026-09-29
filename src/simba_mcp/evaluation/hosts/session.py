"""One bounded provider loop, with provider wire formats supplied as codecs."""

from time import perf_counter

SYSTEM = (
    "Complete only the authorised synthetic task. Preserve exact settings. "
    "Do not repeat already completed preflights. Missing evidence is not a pass. "
    "Never repeat an uncertain write. Return the requested facts as JSON."
)


async def run_session(
    client, tools, prompt, dispatch, budget, checkpoint, *, codec, max_turns=8, system_context=""
):
    """No retries or fallback; checkpoints precede requests and follow billed responses."""
    history = [{"role": "user", "content": prompt}]
    record = {"responses": [], "calls": [], "cost_usd": 0.0, "stop": "turn_limit"}
    started = perf_counter()
    system = SYSTEM + ("\n\n" + system_context if system_context else "")
    for _ in range(max_turns):
        request = codec.request(history, tools, system, budget)
        reservation = budget.reserve(request)
        checkpoint(record)
        response = await client.post(codec.endpoint, json=request)
        if response.status_code != 200:
            record["stop"] = f"provider_http_{response.status_code}"
            # Private checkpoint diagnostics only. Public evidence exporters must
            # not copy provider bodies or headers containing account information.
            record["provider_error"] = {
                "status": response.status_code,
                "retry_after": response.headers.get("retry-after"),
                "body": response.text[:4096],
            }
            checkpoint(record)
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
            checkpoint(record)
        calls, stop, final_text = codec.consume(data, history)
        replies = []
        for call in calls:
            payload, error = await dispatch(call["name"], call["arguments"])
            record["calls"].append(
                {"name": call["name"], "arguments": call["arguments"], "error": error}
            )
            replies.append((call, payload, error))
            checkpoint(record)
        if replies:
            codec.append_results(history, replies)
        elif stop != "pause_turn":
            record["stop"] = stop
            record["final_text"] = final_text
            break
    record["seconds"] = perf_counter() - started
    checkpoint(record)
    return record
