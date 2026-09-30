"""Selective views retain evidence and disclose their local reductions."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from simba_mcp.tools.results import get_model_results


def saved_results():
    """Synthetic GBP results, deliberately unequal spend and mixed section sizes."""
    payload = {
        "model_hash": "result-example",
        "status": "complete",
        "model_type": "mmm",
        "results": {
            "channel_summary": [
                {"Channel": "Search Activity", "Revenue": 500.0, "Spend": 200.0, "ROI": 2.5},
                {"Channel": "TV_activity", "Revenue": 300.0, "Spend": 100.0, "ROI": 3.0},
            ],
            "channel_map": [
                {
                    "channel": "Search",
                    "activity_column": "Search Activity",
                    "spend_column": "search_spend",
                }
            ],
            "coefficients": [
                {
                    "Date": 1735689600000,
                    "Channel": "Search Activity",
                    "Revenue": 200.0,
                    "Spend": 50.0,
                }
            ],
            "contributions": [
                {
                    "Date": 1735689600000,
                    "Search Activity": 20.0,
                    "TV_activity": 15.0,
                    "Base": 80.0,
                    "Overlap": -2.0,
                    "Model": 110.0,
                }
            ],
            "model_config": {"link": "log", "attribution": "removal_lift"},
            "model_stats": [{"Test Name": "Max R_hat", "Output": "1.010", "Status": "success"}],
            "mroi_summary": {
                "channels": [
                    {
                        "channel": "Search",
                        "activity_column": "Search Activity",
                        "current_spend": 100.0,
                        "mroi_median": 1.4,
                    }
                ]
            },
            "response_curves": [
                {
                    "Spend": float(i),
                    "Search Activity": i * 2.0,
                    "Search Activity_lower": i * 1.5,
                    "Search Activity_lower_50": i * 1.8,
                    "Search Activity_upper_50": i * 2.2,
                    "Search Activity_upper": i * 2.5,
                    "TV_activity": i * 3.0,
                }
                for i in range(100)
            ],
        },
    }
    payload["results"]["channel_summary"][0]["Sales"] = 50.0
    payload["results"]["channel_summary"][1]["Sales"] = 30.0
    return payload


@pytest.fixture
def anyio_backend():
    return "asyncio"


def context(payload):
    client = SimpleNamespace(get_model_results=AsyncMock(return_value=payload))
    return (
        SimpleNamespace(
            request_context=SimpleNamespace(
                lifespan_context=SimpleNamespace(client=client, serving_http=False)
            )
        ),
        client,
    )


@pytest.mark.anyio
async def test_disclosure_preserves_source_and_curve_bands():
    source = saved_results()
    source["meta"] = {"window": {"start": "2025-01-01", "end": "2025-02-28"}}
    source["warnings"] = ["Backend warning retained verbatim"]
    original = deepcopy(source)
    ctx, _ = context(source)
    result = await get_model_results(
        "result-example", channels=["search"], max_grid_points=4, ctx=ctx
    )
    assert source == original
    assert result["meta"] == original["meta"]
    assert result["warnings"] == original["warnings"]
    assert result["results"]["contributions"] == original["results"]["contributions"]
    curve = result["results"]["response_curves"]
    assert [row["Spend"] for row in curve] == [0.0, 33.0, 66.0, 99.0]
    assert set(curve[0]) == {
        "Spend",
        "Search Activity",
        "Search Activity_lower",
        "Search Activity_lower_50",
        "Search Activity_upper_50",
        "Search Activity_upper",
    }
    disclosure = result["_mcp_selection"]
    assert disclosure["sections"]["response_curves"]["original_rows"] == 100
    assert disclosure["sections"]["response_curves"]["returned_rows"] == 4
    assert disclosure["sections"]["contributions"]["changed"] is False
    assert disclosure["backend_download_bounded"] is False


@pytest.mark.anyio
@pytest.mark.parametrize("limit", [0, 1, -1])
async def test_legacy_ineffective_grid_limits_disclosed(limit):
    ctx, _ = context(saved_results())
    result = await get_model_results("result-example", max_grid_points=limit, ctx=ctx)
    assert len(result["results"]["response_curves"]) == 100
    assert result["_mcp_selection"]["grid_sampling_applied"] is False
    assert result["_mcp_selection"]["warnings"]


@pytest.mark.anyio
async def test_alias_collision_preserves_both_exact_keys_and_warns():
    source = saved_results()
    source["results"]["channel_summary"].append({"Channel": "search_activity", "ROI": 9.0})
    ctx, _ = context(source)
    result = await get_model_results("result-example", channels=["search"], ctx=ctx)
    assert [row["Channel"] for row in result["results"]["channel_summary"]] == [
        "Search Activity",
        "search_activity",
    ]
    assert result["_mcp_selection"]["ambiguous_channel_aliases"] == {
        "search": ["Search Activity", "search_activity"]
    }


@pytest.mark.anyio
async def test_reserved_metadata_collision_refuses_without_losing_evidence():
    source = saved_results()
    source["_mcp_selection"] = {"backend_field": True}
    original = deepcopy(source)
    ctx, _ = context(source)
    result = await get_model_results("result-example", channels=["search"], ctx=ctx)
    assert result["_status_code"] == 502
    assert source == original


@pytest.mark.anyio
async def test_default_and_csv_unchanged():
    for source, args in [
        (saved_results(), {}),
        ({"format": "csv", "content": "saved"}, {"format": "csv", "channels": ["search"]}),
    ]:
        ctx, _ = context(source)
        assert await get_model_results("result-example", ctx=ctx, **args) is source


@pytest.mark.anyio
async def test_flat_payload_and_missing_channel_are_disclosed():
    source = saved_results()["results"]
    ctx, _ = context(source)
    result = await get_model_results("result-example", channels=["not_present"], ctx=ctx)
    assert result["channel_summary"] == []
    assert result["_mcp_selection"]["unmatched_channel_aliases"] == ["not_present"]
    assert "_mcp_selection" not in source


@pytest.mark.anyio
@pytest.mark.parametrize(
    "link,attribution,overlap",
    [
        ("identity", "additive", False),
        ("log", "aumann_shapley", False),
        ("log", "removal_lift", True),
    ],
)
async def test_attribution_and_margin_evidence_are_never_rewritten(link, attribution, overlap):
    source = saved_results()
    source["results"]["model_config"] = {"link": link, "attribution": attribution}
    if not overlap:
        source["results"]["contributions"][0].pop("Overlap")
        source["results"]["contributions"][0]["Model"] = 112.0
    source["results"]["financials"] = {
        "operating_margin_series": {"2025-01-01": 0.2, "2025-02-01": 0.3}
    }
    source["results"]["mroi_periods"] = {"available": False, "reason": "fitted_before_mroi_periods"}
    source["results"]["channel_summary"].append(
        {"Channel": "zero_activity", "Spend": 0.0, "ROI": None}
    )
    original = deepcopy(source)
    ctx, _ = context(source)
    result = await get_model_results("result-example", channels=["zero"], ctx=ctx)
    assert result["results"]["channel_summary"] == [
        {"Channel": "zero_activity", "Spend": 0.0, "ROI": None}
    ]
    for section in ("contributions", "model_config", "financials", "mroi_periods", "model_stats"):
        assert result["results"][section] == original["results"][section]
    assert source == original


@pytest.mark.anyio
async def test_bucketed_intervals_not_fabricated_and_window_forwarded():
    source = saved_results()
    source["results"]["actual_vs_model"] = [
        {"period_start": "2025-01-01", "period_end": "2025-01-31", "Actual": 120.0, "Model": 110.0}
    ]
    source["meta"] = {
        "window": {"granularity": "month"},
        "not_windowed": {"mroi_summary": "not a per-period section"},
    }
    ctx, client = context(source)
    result = await get_model_results(
        "result-example",
        sections="actual_vs_model,mroi_summary",
        start="2025-01-01",
        end="2025-01-31",
        granularity="month",
        max_grid_points=20,
        ctx=ctx,
    )
    client.get_model_results.assert_awaited_once_with(
        "result-example",
        sections="actual_vs_model,mroi_summary",
        fmt="json",
        start="2025-01-01",
        end="2025-01-31",
        granularity="month",
    )
    assert result["results"]["actual_vs_model"] == source["results"]["actual_vs_model"]
    assert result["meta"]["not_windowed"] == {"mroi_summary": "not a per-period section"}


@pytest.mark.anyio
async def test_display_name_and_activity_column_are_not_a_collision():
    ctx, _ = context(saved_results())
    result = await get_model_results("result-example", channels=["search"], ctx=ctx)
    assert result["_mcp_selection"]["ambiguous_channel_aliases"] == {}
    assert result["results"]["mroi_summary"]["channels"][0]["activity_column"] == "Search Activity"


@pytest.mark.anyio
async def test_size_refusal_then_narrow_read_and_backend_error():
    ctx, _ = context(saved_results())
    refused = await get_model_results(
        "result-example", max_grid_points=20, max_response_bytes=10, ctx=ctx
    )
    assert refused["_status_code"] == 413
    assert "results" not in refused
    accepted = await get_model_results(
        "result-example", max_grid_points=2, max_response_bytes=20000, ctx=ctx
    )
    assert accepted["_mcp_selection"]["grid_sampling_applied"]
    error = {"_status_code": 403, "error": "Access denied"}
    ctx, _ = context(error)
    assert await get_model_results("result-example", channels=["search"], ctx=ctx) is error


@pytest.mark.anyio
async def test_prediction_payload_passes_through_without_adding_requests():
    source = {
        "results": {"prediction_window": {"available": True, "rows": [{"actual": 2.0}]}},
        "audit": {"untouched": False},
    }
    ctx, client = context(source)
    result = await get_model_results(
        "result-example", sections="prediction_window", channels=["search"], ctx=ctx
    )
    assert result["results"] == source["results"]
    assert result["audit"] == source["audit"]
    assert client.get_model_results.await_count == 1
