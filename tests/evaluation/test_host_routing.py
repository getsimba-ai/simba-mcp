"""Shared-ledger and actual-handler instrumentation, without paid execution."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from simba_mcp.api_client import SimbaAPIClient
from simba_mcp.evaluation.hosts.budget import Budget
from simba_mcp.evaluation.hosts.routing import RoutingDispatch, complete_task_usage, routing_usage
from simba_mcp.guidance.routing import MODEL


@pytest.fixture
def anyio_backend():
    return "asyncio"


def request():
    return {"model": MODEL, "input": "Explain ROI"}


def test_decisions_share_main_budget_and_unknown_reservations_carry_forward():
    budget = Budget(1, prior=0.9)
    decision_reservation = budget.reserve_decision(request(), input_rate=0.1)
    main_reservation = budget.reserve({"max_tokens": 100})
    budget.settle({"input_tokens": 100, "output_tokens": 5}, main_reservation)
    with pytest.raises(ValueError, match="retained"):
        budget.settle_decision({}, decision_reservation, input_rate=0.1)
    assert budget.reserved == pytest.approx(decision_reservation)
    carried = Budget(1, prior=budget.prior + budget.charged + budget.reserved)
    assert carried.prior > budget.prior
    assert carried.reserve_decision(request(), input_rate=0.1) > 0
    with pytest.raises(RuntimeError, match="exhausted"):
        Budget(0.0001).reserve_decision(request(), input_rate=0.1)


@pytest.mark.parametrize("rate", [None, True, 0.09, float("nan"), -1])
def test_price_is_explicit_finite_and_never_understates_base(rate):
    with pytest.raises(ValueError, match="price"):
        Budget(1).reserve_decision(request(), input_rate=rate)


def test_known_overrun_is_charged_and_stops_instead_of_resetting_budget():
    budget = Budget(1)
    reservation = budget.reserve_decision(request(), input_rate=0.1)
    with pytest.raises(RuntimeError, match="exceeded"):
        budget.settle_decision({"input_tokens": 9000}, reservation, input_rate=0.1)
    assert budget.charged == pytest.approx(0.0009) and budget.reserved == 0


@pytest.mark.anyio
async def test_real_handler_http_charge_and_domain_grading_remain_separate():
    requests, snapshots = [], []
    budget = Budget(1)

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "outcome": "recommended",
                "workflow": "results",
                "confidence": 0.97,
                "model": MODEL,
                "input_tokens": 123,
            },
        )

    client = SimbaAPIClient("https://example.invalid", "synthetic")
    client._client = httpx.AsyncClient(
        base_url=client.base_url, headers=client._headers, transport=httpx.MockTransport(handle)
    )
    domain = AsyncMock(return_value=({"evidence": "synthetic"}, False))
    domain.completed = 0
    dispatch = RoutingDispatch(
        domain,
        client,
        budget,
        lambda _: snapshots.append(budget.reserved),
        visible=["recommend_workflow", "get_model_results"],
        input_rate=0.1,
    )
    try:
        result, error = await dispatch("recommend_workflow", {"request": "Explain ROI"})
        assert not error and result["suggested_tools"] == ["get_model_results"]
        assert len(requests) == 1 and snapshots[0] > 0
        assert requests[0].headers["Authorization"] == "Bearer synthetic"
        assert requests[0].url.path == "/api/v1/mcp/workflow-recommendations"
        assert budget.charged == pytest.approx(0.0000123) and budget.reserved == 0
        assert dispatch.completed == 0 and domain.await_count == 0
        assert routing_usage(dispatch.routing_attempts)["input_tokens"] == 123
        await dispatch("get_model_results", {"model_hash": "synthetic"})
        domain.assert_awaited_once()
    finally:
        await client.close()


@pytest.mark.anyio
@pytest.mark.parametrize("reason,unknown", [("disabled", False), ("provider_error", True)])
async def test_prepaid_fallback_and_unknown_billing_are_distinct(reason, unknown):
    client = SimpleNamespace(
        workflow_request=AsyncMock(return_value={"outcome": "fallback", "reason": reason})
    )
    budget = Budget(1)
    dispatch = RoutingDispatch(
        AsyncMock(),
        client,
        budget,
        lambda _: None,
        visible=["recommend_workflow"],
        input_rate=0.1,
    )
    await dispatch("recommend_workflow", {"request": "Explain ROI"})
    summary = routing_usage(dispatch.routing_attempts)
    assert bool(budget.reserved) == unknown
    assert summary["unknown_billing_attempts"] == int(unknown)
    assert (summary["input_tokens"] is None) == unknown


@pytest.mark.anyio
async def test_checkpoint_failure_prevents_submission():
    client = SimpleNamespace(workflow_request=AsyncMock())

    def fail(_):
        raise OSError("synthetic checkpoint failure")

    dispatch = RoutingDispatch(
        AsyncMock(),
        client,
        Budget(1),
        fail,
        visible=["recommend_workflow"],
        input_rate=0.1,
    )
    with pytest.raises(OSError):
        await dispatch("recommend_workflow", {"request": "Explain ROI"})
    client.workflow_request.assert_not_awaited()


def test_combined_usage_includes_cache_and_selector_without_double_counting_latency():
    record = {
        "stop": "end_turn",
        "seconds": 2,
        "cost_usd": 0.1,
        "responses": [{"usage": {"input_tokens": 100, "cache_read_input_tokens": 20}}],
    }
    attempt = {"input_tokens": 10, "cost_usd": 0.000001, "seconds": 0.2}
    total = complete_task_usage(record, [attempt])
    assert total["total_input_tokens"] == 130
    assert total["seconds"] == 2
    assert total["total_cost_usd"] == pytest.approx(0.100001)
    assert total["accounting_complete"]
    interrupted = complete_task_usage({**record, "stop": "session_error"}, [attempt])
    assert interrupted["total_input_tokens"] is None
    assert interrupted["total_cost_usd"] is None and not interrupted["accounting_complete"]


@pytest.mark.parametrize("cost", [None, True, -1, float("nan")])
def test_missing_or_invalid_main_billing_cannot_be_zero_cost(cost):
    record = {
        "responses": [{"usage": {"input_tokens": 10}}],
        "stop": "end_turn",
        "seconds": 1,
    }
    if cost is not None:
        record["cost_usd"] = cost
    usage = complete_task_usage(record, [])
    assert usage["total_cost_usd"] is None
    assert usage["accounting_complete"] is False
