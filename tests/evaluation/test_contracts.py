"""Host reports must keep missing observations and unsupported modes explicit."""

import pytest
from pydantic import ValidationError

from simba_mcp.evaluation.contracts import HostTrial


def valid_report():
    return {
        "case_id": "example_case",
        "fixture_sha256": "a" * 64,
        "configuration_sha256": "b" * 64,
        "mcp_version": "example-version",
        "host_version": "example-host",
        "model": "example-model",
        "repetition": 0,
        "cache_condition": "unknown",
        "supported_configuration": True,
        "outcome": "pass",
        "assertions": {"expected_result": True},
        "unintended_writes": 0,
        "tool_calls": 2,
        "model_turns": 2,
        "discovery_calls": 1,
        "backend_attempts": None,
        "payload_bytes": None,
        "payload_basis": "unavailable",
        "latency_seconds": 1.0,
        "usage": None,
        "unavailable": {
            "backend_attempts": "not observed",
            "payload_bytes": "not observed",
            "usage": "not supplied",
        },
    }


def test_host_report_accepts_explicit_unknowns_and_provider_usage():
    data = valid_report()
    assert HostTrial.model_validate(data).usage is None
    data["usage"] = {
        "input_tokens": 100,
        "output_tokens": 20,
        "cached_input_tokens": 80,
        "source": "provider_response",
        "input_includes_cached": True,
    }
    assert HostTrial.model_validate(data).usage.input_tokens == 100


@pytest.mark.parametrize(
    "changes",
    [
        {"supported_configuration": False},
        {"assertions": {}},
        {"assertions": {"required_holdout": False}},
        {"unintended_writes": 1},
        {"unavailable": {}},
        {"model_turns": 0},
        {"latency_seconds": float("nan")},
        {"payload_bytes": 10},
        {"raw_transcript": "not part of report"},
        {
            "usage": {
                "input_tokens": 10,
                "output_tokens": 2,
                "source": "tokenizer_estimate",
                "input_includes_cached": False,
            }
        },
    ],
)
def test_invalid_or_misleading_host_reports_are_rejected(changes):
    with pytest.raises(ValidationError):
        HostTrial.model_validate({**valid_report(), **changes})
