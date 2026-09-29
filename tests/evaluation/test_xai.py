"""Provider boundary checks without paid inference or a real backend."""

import json
from types import SimpleNamespace

import httpx
import pytest

from simba_mcp.evaluation.hosts.budget import Budget
from simba_mcp.evaluation.hosts.models import GROK, SONNET, model_configuration
from simba_mcp.evaluation.hosts.xai import definitions, session


@pytest.fixture
def anyio_backend():
    return "asyncio"


def response(output, **overrides):
    return {
        "model": GROK,
        "status": "completed",
        "output": output,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "output_tokens_details": {"reasoning_tokens": 20},
            "cost_in_usd_ticks": 5000000,
        },
        **overrides,
    }


def test_xai_schema_and_mode_boundaries():
    tool = SimpleNamespace(name="read", description="Read", input_schema={"type": "object"})
    actual = definitions([tool], "eager")
    assert actual == [
        {
            "type": "function",
            "name": "read",
            "description": "Read",
            "parameters": {"type": "object"},
        }
    ]
    actual[0]["parameters"]["changed"] = True
    assert tool.input_schema == {"type": "object"}
    with pytest.raises(ValueError, match="eager"):
        definitions([tool], "deferred")


def test_xai_actual_billing_and_unknown_usage_reservations():
    budget = Budget(500, prior=67.781696, model=GROK)
    request = model_configuration(GROK)["request"]
    reservation = budget.reserve(request)
    # Provider billing includes reasoning and cache discounts, not charged twice.
    assert budget.settle(response([])["usage"], reservation) == pytest.approx(0.0005)
    assert budget.reserved == 0
    reservation = budget.reserve(request)
    with pytest.raises(ValueError, match="billing"):
        budget.settle({"input_tokens": 100, "output_tokens": 50}, reservation)
    assert budget.reserved == reservation
    with pytest.raises(RuntimeError, match="exhausted"):
        Budget(67.79, prior=67.781696, model=GROK).reserve(request)
    with pytest.raises(ValueError, match="limit"):
        budget.reserve({"model": GROK})
    with pytest.raises(ValueError, match="override"):
        Budget(2, model=SONNET, reasoning_effort="low")
    with pytest.raises(ValueError, match="override"):
        Budget(2, model=GROK, reasoning_effort="off")


@pytest.mark.anyio
@pytest.mark.parametrize("effort", [None, "low"])
async def test_xai_roundtrips_reasoning_and_all_local_tool_results(effort):
    thinking = {"type": "reasoning", "id": "r", "encrypted_content": "opaque-test-value"}
    calls = [
        {
            "type": "function_call",
            "call_id": str(i),
            "name": "read",
            "arguments": json.dumps({"index": i}),
        }
        for i in range(2)
    ]
    outputs = [
        response([thinking, *calls]),
        response([{"type": "message", "content": [{"type": "output_text", "text": "{}"}]}]),
    ]
    requests, executed = [], []

    def transport(request):
        assert str(request.url) == "https://api.x.ai/v1/responses"
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=outputs.pop(0))

    async def dispatch(name, args):
        executed.append(args["index"])
        return {"value": args["index"]}, bool(args["index"])

    budget = Budget(2, model=GROK, reasoning_effort=effort)
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        record = await session(client, [], "read", dispatch, budget, lambda _: None)
    assert executed == [0, 1]
    assert requests[1]["input"][1:4] == [thinking, *calls]
    assert [x["call_id"] for x in requests[1]["input"][-2:]] == ["0", "1"]
    assert requests[0]["reasoning"] == {"effort": effort or "medium"}
    assert requests[0]["model"] == GROK
    assert requests[0]["store"] is False
    assert record["final_text"] == "{}" and record["stop"] == "end_turn"
    assert record["cost_usd"] == pytest.approx(0.001)
    assert budget.reserved == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fault", ["http", "rate_limit", "usage", "model", "arguments", "incomplete", "server_tool"]
)
async def test_xai_errors_never_dispatch_or_retry(fault):
    called = []
    data = response([{"type": "function_call", "call_id": "c", "name": "write", "arguments": "{}"}])
    if fault == "usage":
        data["usage"].pop("cost_in_usd_ticks")
    elif fault == "model":
        data["model"] = "unexpected"
    elif fault == "arguments":
        data["output"][0]["arguments"] = "[]"
    elif fault == "incomplete":
        data["status"] = "incomplete"
    elif fault == "server_tool":
        data["output"].append({"type": "web_search_call"})

    def transport(request):
        called.append(True)
        if fault == "rate_limit":
            return httpx.Response(429, text="synthetic limit " * 500, headers={"Retry-After": "60"})
        return httpx.Response(500 if fault == "http" else 200, json=data)

    async def dispatch(*_):
        raise AssertionError("Invalid response must not execute tools")

    budget = Budget(2, model=GROK)
    checkpoints = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises((RuntimeError, ValueError)):
            await session(
                client, [], "read", dispatch, budget, lambda r: checkpoints.append(dict(r))
            )
    assert len(called) == 1
    assert (budget.reserved > 0) == (fault in ("http", "rate_limit", "usage"))
    if fault == "rate_limit":
        error = checkpoints[-1]["provider_error"]
        assert error["status"] == 429 and error["retry_after"] == "60"
        assert error["body"] == ("synthetic limit " * 500)[:4096]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "diagnostic,trial_filter",
    [
        (False, None),
        (True, None),
        (False, ["baseline:1"]),
        (False, ["candidate:9"]),
        (True, ["candidate:0"]),
        (False, ["baseline:1", "baseline:1"]),
    ],
)
async def test_xai_command_reuses_frozen_cases_and_selects_only_xai_key(
    tmp_path, monkeypatch, diagnostic, trial_filter
):
    from simba_mcp.evaluation.hosts import __main__ as command
    from simba_mcp.evaluation.hosts import xai
    from simba_mcp.guidance import read_guidance

    requests = []

    def transport(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json=response(
                [{"type": "message", "content": [{"type": "output_text", "text": "{}"}]}]
            ),
        )

    def client(key):
        assert key == "synthetic-xai-key"
        return httpx.AsyncClient(transport=httpx.MockTransport(transport))

    monkeypatch.setattr(xai, "client", client)
    monkeypatch.setenv("XAI_API_KEY", "synthetic-xai-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    baseline = tmp_path / "guidance.json"
    baseline.write_text(
        json.dumps(
            {
                s: read_guidance("results", s)
                for s in ("entrypoint", "interpretation", "tool-reference")
            }
        )
    )
    output = tmp_path / "comparison.json"
    operation = command.run(
        SimpleNamespace(
            output=output,
            cap_usd=10,
            prior_usd=2,
            samples=2,
            mode="eager",
            case="v3_kpi_revenue_basis",
            model=GROK,
            reasoning_effort="low",
            results_robust=True,
            results_acceptance=True,
            results_acceptance_packet="v3",
            results_selection_validation=True,
            results_model_diagnostic=diagnostic,
            results_prompt="paraphrase",
            results_baseline=baseline,
            results_trial=trial_filter,
        )
    )
    if trial_filter and (diagnostic or trial_filter != ["baseline:1"]):
        with pytest.raises(ValueError, match="Trial selection"):
            await operation
        assert not requests and not output.exists()
        return
    await operation
    report = json.loads(output.read_text())
    count = 1 if trial_filter else 2 if diagnostic else 4
    assert report["status"] == "complete" and len(requests) == count
    assert report["configuration"]["model"] == GROK
    assert report["configuration"]["model_configuration"]["request"]["reasoning"] == {
        "effort": "low"
    }
    assert report["configuration"]["results_selection_validation"]
    assert all("combined Sales" in t["prompt"] for t in report["trials"])
    assert all(t["prompt_variant"] == "paraphrase" for t in report["trials"])
    assert report["budget"]["charged"] == pytest.approx(count * 0.0005)
    assert report["budget"]["reserved"] == 0
    if trial_filter:
        assert [(t["view"], t["repetition"]) for t in report["trials"]] == [("baseline", 1)]
        assert report["configuration"]["results_trial"] == trial_filter
        assert report["assessment"]["status"] == "invalid"
        assert not report["assessment"]["accepted"]
    if diagnostic:
        assert not report["assessment"]["accepted"]
        assert {t["view"] for t in report["trials"]} == {"candidate"}


@pytest.mark.anyio
async def test_billed_overrun_is_checkpointed_before_stopping():
    data = response(
        [], usage={"input_tokens": 100, "output_tokens": 50, "cost_in_usd_ticks": 10_000_000_000}
    )
    snapshots = []

    async def dispatch(*_):
        raise AssertionError("Over-budget response must not execute tools")

    budget = Budget(2, model=GROK)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data))
    ) as client:
        with pytest.raises(RuntimeError, match="exceeded reservation"):
            await session(
                client,
                [],
                "read",
                dispatch,
                budget,
                lambda r: snapshots.append(json.loads(json.dumps(r))),
            )
    assert budget.charged == snapshots[-1]["cost_usd"] == 1
    assert budget.reserved == 0
    assert snapshots[-1]["responses"] == [data]
