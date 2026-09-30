"""The configuration report matches runtime parsers and does not reveal secrets."""

import json

import pytest

from simba_mcp.api_client import DEFAULT_TIMEOUT
from simba_mcp.auth import _local_files_denial_reason, local_files_effective
from simba_mcp.configuration import (
    ConfigurationError,
    coverage_errors,
    effective_configuration,
    main,
    referenced_environment_names,
)
from simba_mcp.oauth import oauth_enabled
from simba_mcp.runtime import MAX_REQUEST_BODY_BYTES, MAX_UPLOAD_BYTES, _response_byte_limit
from simba_mcp.telemetry import get_sink, stderr_sink


class Args:
    def __init__(self, **kwargs):
        self.transport = kwargs.get("transport", "stdio")
        self.host = kwargs.get("host", "0.0.0.0")
        self.port = kwargs.get("port", 8100)
        self.profile = kwargs.get("profile")
        self.deployment = kwargs.get("deployment", "cli")


@pytest.fixture(autouse=True)
def clear_server_environment(monkeypatch):
    for name in (
        "SIMBA_API_URL",
        "SIMBA_API_KEY",
        "SIMBA_API_REQUEST_POLICY_JSON",
        "SIMBA_API_MAX_ENCODED_BYTES",
        "SIMBA_API_MAX_DECODED_BYTES",
        "SIMBA_TOOL_DESCRIPTIONS",
        "SIMBA_TOOL_PROFILE",
        "SIMBA_MCP_ALLOW_LOCAL_FILES",
        "SIMBA_MCP_METRICS",
        "MCP_OAUTH_ENABLED",
        "SIMBA_PUBLIC_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults_match_runtime_and_omit_secrets():
    report = effective_configuration(Args())
    assert report["profile"] == {"value": "full", "source": "default"}
    assert report["description_mode"]["value"] == "legacy"
    assert report["request_policy"]["enabled"] is False
    assert report["request_policy"]["fallback_timeout_seconds"] == DEFAULT_TIMEOUT
    assert report["max_encoded_bytes"]["value"] is None
    assert report["api_key"] == {"configured": False, "used": False, "reason": "absent"}
    assert report["local_files"] == {"allowed": True, "source": "stdio-default"}
    assert report["oauth"]["enabled"] is oauth_enabled()
    assert report["ceilings"]["max_upload_bytes"] == MAX_UPLOAD_BYTES
    assert report["ceilings"]["max_request_body_bytes"] == MAX_REQUEST_BODY_BYTES
    assert "SIMBA_API_KEY" in referenced_environment_names()


def test_profile_argument_overrides_environment_without_changing_permissions(monkeypatch):
    monkeypatch.setenv("SIMBA_TOOL_PROFILE", "marketer")
    report = effective_configuration(Args(profile="reviewer"))
    assert report["profile"] == {"value": "reviewer", "source": "argument"}
    monkeypatch.setenv("SIMBA_TOOL_PROFILE", "not-a-profile")
    with pytest.raises(ConfigurationError, match="SIMBA_TOOL_PROFILE"):
        effective_configuration(Args())


def test_http_ignores_operator_key_and_denies_local_files(monkeypatch):
    monkeypatch.setenv("SIMBA_API_KEY", "simba_sk_operator")
    report = effective_configuration(Args(transport="streamable-http"))
    assert report["api_key"] == {
        "configured": True,
        "used": False,
        "reason": "ignored_in_http_mode",
    }
    assert report["local_files"] == {"allowed": False, "source": "network-default"}
    assert "simba_sk_operator" not in json.dumps(report)


def test_invalid_policy_and_limits_do_not_echo_the_supplied_value(monkeypatch, capsys):
    monkeypatch.setenv("SIMBA_API_REQUEST_POLICY_JSON", '{"secret":"simba_sk_policy"}')
    assert main([]) == 2
    assert "simba_sk_policy" not in capsys.readouterr().out
    monkeypatch.setenv("SIMBA_API_REQUEST_POLICY_JSON", "")
    monkeypatch.setenv("SIMBA_API_MAX_ENCODED_BYTES", "simba_sk_limit")
    assert main([]) == 2
    assert "simba_sk_limit" not in capsys.readouterr().out


def test_policy_false_disables_admission_and_keeps_the_fallback(monkeypatch):
    monkeypatch.setenv("SIMBA_API_REQUEST_POLICY_JSON", "false")
    report = effective_configuration(Args())
    assert report["request_policy"]["enabled"] is False
    assert report["request_policy"]["source"] == "disabled"


def test_url_userinfo_is_omitted(monkeypatch):
    monkeypatch.setenv("SIMBA_API_URL", "https://user:simba_sk_url@example.test/base?token=secret")
    report = effective_configuration(Args())
    assert report["api_url"]["value"] == "https://example.test/base"
    assert report["api_url"]["credential_omitted"] is True
    rendered = json.dumps(report)
    assert "simba_sk_url" not in rendered
    assert "token=secret" not in rendered


def test_metrics_and_oauth_use_the_runtime_rules(monkeypatch):
    monkeypatch.setenv("SIMBA_MCP_METRICS", "stderr")
    assert effective_configuration(Args())["metrics"]["enabled"] is True
    assert get_sink() is stderr_sink
    monkeypatch.setenv("SIMBA_MCP_METRICS", "1")
    report = effective_configuration(Args())
    assert report["metrics"]["enabled"] is False
    assert get_sink() is None
    assert any("stderr" in warning for warning in report["warnings"])
    monkeypatch.setenv("MCP_OAUTH_ENABLED", "yes")
    monkeypatch.setenv("SIMBA_PUBLIC_URL", "https://example.test")
    assert effective_configuration(Args())["oauth"] == {
        "enabled": True,
        "public_url": "https://example.test",
    }
    assert oauth_enabled() is True


def test_byte_limits_use_the_runtime_parser(monkeypatch):
    monkeypatch.setenv("SIMBA_API_MAX_DECODED_BYTES", "2048")
    report = effective_configuration(Args())
    assert report["max_decoded_bytes"]["value"] == 2048
    assert report["max_decoded_bytes"]["value"] == _response_byte_limit(
        "SIMBA_API_MAX_DECODED_BYTES"
    )


def test_local_file_decision_keeps_the_existing_messages(monkeypatch):
    assert local_files_effective("maybe", False) == (True, "stdio-default")
    assert local_files_effective("maybe", True) == (False, "network-default")
    monkeypatch.setattr("simba_mcp.auth.runtime._serving_http", True)
    monkeypatch.delenv("SIMBA_MCP_ALLOW_LOCAL_FILES", raising=False)
    assert "network transports" in _local_files_denial_reason()
    monkeypatch.setenv("SIMBA_MCP_ALLOW_LOCAL_FILES", "0")
    assert "set to '0'" in _local_files_denial_reason()


def test_inventory_covers_server_code_and_generated_docs():
    assert coverage_errors() == []
