from dataclasses import replace

import pytest

from simba_mcp.evaluation.hosts.result_calibration import calibrate
from simba_mcp.evaluation.hosts.result_period_calibration import period_fixture, period_labels
from simba_mcp.evaluation.hosts.result_period_evidence import monthly_evidence
from simba_mcp.evaluation.hosts.result_selection import ResultSelectionDispatch, ResultTask
from simba_mcp.server import create_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


def task():
    return ResultTask(
        "monthly_calibration",
        "Compare January and February revenue and spend.",
        frozenset({"period_revenue_rows", "channel_map"}),
        {"jan_revenue": 400, "jan_spend": 100, "feb_revenue": 200, "feb_spend": 100},
        fixture=period_fixture(),
        channel="activity_a",
        evidence_window={"start": "2025-01-01", "end": "2025-02-28"},
        period_evidence_granularity="month",
    )


@pytest.mark.parametrize(
    "name,contract,payload,window,expected", period_labels(), ids=[x[0] for x in period_labels()]
)
def test_labelled_monthly_evidence(name, contract, payload, window, expected):
    _, observed = monthly_evidence(contract, payload, window)
    assert len({(r["period_start"], r["period_end"], r["Channel"]) for r in observed}) == expected


def test_versions_and_calibration():
    assert calibrate(grader_version=19)["passed"]
    assert len(calibrate(grader_version=19)["period_evidence_cases"]) == 28
    assert "period_evidence_cases" not in calibrate(grader_version=18)
    with pytest.raises(ValueError, match="requires grader19"):
        ResultSelectionDispatch(create_server("compact"), task(), grader_version=18)


@pytest.mark.anyio
async def test_monthly_summary_atoms_contribute_before_complete_and_duplicate_does_not():
    t = task()
    d = ResultSelectionDispatch(create_server("compact"), t, grader_version=19)
    await d("get_model_results", {"model_hash": "calibration-periods", "sections": "channel_map"})
    for end in ("2025-01-31", "2025-01-31", "2025-02-28"):
        start = "2025-01-01" if end.endswith("01-31") else "2025-02-01"
        await d(
            "get_model_results",
            {
                "model_hash": "calibration-periods",
                "sections": "channel_summary",
                "start": start,
                "end": end,
                "granularity": "month",
            },
        )
        assert d.calls[-1]["added_period_evidence_atoms"] == (0 if len(d.calls) == 3 else 1)
    assert d.noncontributing_result_calls == 1
    assert all(d.grade(t.expected).values())


@pytest.mark.anyio
async def test_bucketed_months_require_explicit_monthly_task_contract():
    t = task()
    for version, granularity, expected in (
        (18, "native", False),
        (19, "native", False),
        (19, "month", True),
    ):
        d = ResultSelectionDispatch(
            create_server("compact"),
            replace(t, period_evidence_granularity=granularity),
            grader_version=version,
        )
        await d(
            "get_model_results",
            {
                "model_hash": "calibration-periods",
                "sections": "channel_map,coefficients",
                "start": "2025-01-01",
                "end": "2025-02-28",
                "granularity": "month",
            },
        )
        assert d.grade(t.expected)["required_evidence"] is expected


@pytest.mark.anyio
async def test_missing_identity_still_rejected():
    t = task()
    d = ResultSelectionDispatch(create_server("compact"), t, grader_version=19)
    await d(
        "get_model_results",
        {
            "model_hash": "calibration-periods",
            "sections": "coefficients",
            "start": "2025-01-01",
            "end": "2025-02-28",
            "granularity": "month",
        },
    )
    assert not d.grade(t.expected)["required_evidence"]


@pytest.mark.anyio
async def test_later_conflict_invalidates_previously_complete_evidence(monkeypatch):
    from simba_mcp.evaluation.hosts import result_selection

    t = task()
    d = ResultSelectionDispatch(create_server("compact"), t, grader_version=19)
    args = {
        "model_hash": "calibration-periods",
        "sections": "channel_map,coefficients",
        "start": "2025-01-01",
        "end": "2025-02-28",
        "granularity": "month",
    }
    await d("get_model_results", args)
    assert d.grade(t.expected)["required_evidence"]
    original = result_selection.run_case

    async def contradictory(case, **kwargs):
        case = case.model_copy(deep=True)
        case.steps[0].exchanges[0].response["results"]["coefficients"][0]["Revenue"] = 999
        return await original(case, **kwargs)

    monkeypatch.setattr(result_selection, "run_case", contradictory)
    await d("get_model_results", args)
    assert d.monthly_evidence_conflicts
    assert d.calls[-1]["period_evidence_conflict"] is True
    assert not d.grade(t.expected)["required_evidence"]
    monkeypatch.setattr(result_selection, "run_case", original)
    await d("get_model_results", args)
    assert not d.grade(t.expected)["required_evidence"]


@pytest.mark.parametrize(
    "start,end",
    [("2025-01-08", "2025-02-28"), ("2025-01-01", "2025-02-20"), ("20250101", "20250228")],
)
def test_partial_month_contract_cannot_be_widened(start, end):
    with pytest.raises(ValueError, match="complete months"):
        ResultSelectionDispatch(
            create_server("compact"),
            replace(task(), evidence_window={"start": start, "end": end}),
            grader_version=19,
        )


@pytest.mark.parametrize("granularity", ["native", "month"])
def test_packet_contract_freezes_explicit_period_semantics(granularity):
    from simba_mcp.evaluation.hosts.workflow_packet import ResultContract

    contract = ResultContract(
        id="period_contract",
        required_sections=["period_revenue_rows"],
        fixture=period_fixture(),
        evidence_window={"start": "2025-01-01", "end": "2025-02-28"},
        period_evidence_granularity=granularity,
    )
    assert contract.model_dump()["period_evidence_granularity"] == granularity


@pytest.mark.parametrize(
    "window",
    [
        None,
        {"start": "2025-01-08", "end": "2025-02-28"},
        {"start": "2025-01-01", "end": "2025-02-20"},
    ],
)
def test_packet_monthly_contract_requires_complete_months(window):
    from simba_mcp.evaluation.hosts.workflow_packet import ResultContract

    with pytest.raises(ValueError, match="complete calendar months"):
        ResultContract(
            id="period_contract",
            required_sections=["period_revenue_rows"],
            fixture=period_fixture(),
            evidence_window=window,
            period_evidence_granularity="month",
        )


@pytest.mark.anyio
async def test_cli_freezes_monthly_contract_without_provider(tmp_path, monkeypatch):
    import json
    from dataclasses import asdict
    from types import SimpleNamespace

    from simba_mcp.evaluation.hosts import __main__ as command
    from simba_mcp.evaluation.hosts import xai

    t = task()
    contract = asdict(t)
    contract.pop("prompt")
    contract.pop("expected")
    packet = tmp_path / "packet.json"
    packet.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "packet_id": "monthly-contract-cli",
                "synthetic_only": True,
                "tasks": [
                    {
                        "kind": "result",
                        "prompt": t.prompt,
                        "expected": t.expected,
                        "contract": contract,
                    }
                ],
            },
            default=lambda x: sorted(x),
        )
    )
    args = SimpleNamespace(
        output=tmp_path / "report.json",
        cap_usd=2,
        prior_usd=0,
        samples=1,
        mode="eager",
        case=t.id,
        workflow_suite="rlc01",
        workflow_packet=packet,
        model="grok-4.7",
        reasoning_effort="low",
        grader_version=19,
    )

    async def fake_session(*values, **kwargs):
        return {
            "final_text": json.dumps(t.expected),
            "cost_usd": 0,
            "calls": [],
            "stop": "end_turn",
        }

    monkeypatch.setenv("XAI_API_KEY", "synthetic-never-sent")
    monkeypatch.setattr(xai, "session", fake_session)
    await command.run(args)
    report = json.loads(args.output.read_text())
    assert report["tasks"][0]["case"]["period_evidence_granularity"] == "month"
    assert (
        report["configuration"]["workflow_packet"]["document"]["tasks"][0]["contract"][
            "period_evidence_granularity"
        ]
        == "month"
    )
    assert report["configuration"]["grader_version"] == 19
