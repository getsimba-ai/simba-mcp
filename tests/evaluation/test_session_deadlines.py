"""Session deadlines retain accounting and partial execution evidence."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from simba_mcp.evaluation.hosts.session import run_session


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Budget:
    charged = 0
    reserved = 0

    def reserve(self, request):
        self.reserved += 1
        return 1

    def settle(self, usage, reservation):
        self.reserved -= reservation
        self.charged += 0.1


class Codec:
    endpoint = "synthetic"

    def request(self, *args):
        return {}

    def consume(self, *args):
        return [{"name": "write", "arguments": {}}], "tool_use", ""


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["provider", "dispatch"])
async def test_timeout_preserves_partial_evidence(phase):
    saved = []
    budget = Budget()

    async def post(*args, **kwargs):
        if phase == "provider":
            await asyncio.sleep(10)
        return SimpleNamespace(status_code=200, json=lambda: {"usage": {}})

    async def dispatch(*args):
        await asyncio.sleep(10)

    with pytest.raises(TimeoutError):
        await run_session(
            SimpleNamespace(post=post),
            [],
            "task",
            dispatch,
            budget,
            lambda value: saved.append(deepcopy(value)),
            codec=Codec(),
            session_timeout_seconds=0.02,
        )
    record = saved[-1]
    assert record["stop"] == "session_timeout"
    assert record["seconds"] > 0
    if phase == "provider":
        assert budget.reserved == 1
        assert record["calls"] == []
    else:
        assert budget.reserved == 0
        assert record["cost_usd"] == 0.1
        assert record["calls"][0]["status"] == "interrupted"
        assert record["dispatch_seconds"] > 0


@pytest.mark.anyio
async def test_cancellation_is_recorded_without_replay():
    saved = []
    budget = Budget()

    async def post(*args, **kwargs):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await run_session(
            SimpleNamespace(post=post),
            [],
            "task",
            None,
            budget,
            lambda value: saved.append(deepcopy(value)),
            codec=Codec(),
        )
    assert saved[-1]["stop"] == "cancelled"
    assert saved[-1]["seconds"] >= 0
    assert budget.reserved == 1


@pytest.mark.anyio
async def test_final_checkpoint_failure_preserves_original_error():
    count = 0

    async def post(*args, **kwargs):
        raise ValueError("original")

    def checkpoint(record):
        nonlocal count
        count += 1
        if count > 1:
            raise OSError("checkpoint")

    with pytest.raises(ValueError, match="original") as raised:
        await run_session(
            SimpleNamespace(post=post), [], "task", None, Budget(), checkpoint, codec=Codec()
        )
    assert "OSError" in raised.value.__notes__[0]


@pytest.mark.anyio
async def test_operation_timeout_is_not_session_deadline():
    saved = []

    async def post(*args, **kwargs):
        raise TimeoutError("operation")

    with pytest.raises(TimeoutError):
        await run_session(
            SimpleNamespace(post=post),
            [],
            "task",
            None,
            Budget(),
            lambda value: saved.append(deepcopy(value)),
            codec=Codec(),
        )
    assert saved[-1]["stop"] == "operation_timeout"


@pytest.mark.anyio
async def test_settlement_error_survives_checkpoint_error():
    class Overrun(Budget):
        def settle(self, usage, reservation):
            super().settle(usage, reservation)
            raise RuntimeError("overrun")

    async def post(*args, **kwargs):
        return SimpleNamespace(status_code=200, json=lambda: {"usage": {}})

    saved = []

    def checkpoint(record):
        saved.append(deepcopy(record))
        if record["responses"]:
            raise OSError("checkpoint")

    with pytest.raises(RuntimeError, match="overrun") as raised:
        await run_session(
            SimpleNamespace(post=post), [], "task", None, Overrun(), checkpoint, codec=Codec()
        )
    assert saved[-1]["cost_usd"] == 0.1
    assert saved[-1]["error_type"] == "RuntimeError"
    assert any("OSError" in note for note in raised.value.__notes__)
