"""Versioned host-side evaluation contract; validation does not certify evidence."""

from typing import Literal

from pydantic import Field, model_validator

from .evaluation import StrictModel


class Usage(StrictModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    source: Literal["provider_response"]
    # Providers differ: document whether input includes cached tokens.
    input_includes_cached: bool


class HostTrial(StrictModel):
    schema_version: Literal[1] = 1
    case_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    fixture_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    configuration_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    mcp_version: str = Field(min_length=1)
    host_version: str = Field(min_length=1)
    model: str = Field(min_length=1)
    repetition: int = Field(ge=0)
    cache_condition: Literal["cold", "warm", "unknown"]
    supported_configuration: bool
    outcome: Literal["pass", "fail", "untested"]
    assertions: dict[str, bool]
    unintended_writes: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    model_turns: int = Field(ge=0)
    discovery_calls: int = Field(ge=0)
    backend_attempts: int | None = Field(ge=0)
    payload_bytes: int | None = Field(ge=0)
    payload_basis: Literal["mcp_http_body", "call_tool_result_json", "unavailable"]
    latency_seconds: float | None = Field(ge=0, allow_inf_nan=False)
    usage: Usage | None
    unavailable: dict[str, str]

    @model_validator(mode="after")
    def check_evidence(self):
        if not self.supported_configuration and self.outcome != "untested":
            raise ValueError("Unsupported configurations must be untested")
        if self.outcome == "pass" and (
            not self.assertions
            or not all(self.assertions.values())
            or self.unintended_writes
            or self.model_turns == 0
            or self.tool_calls == 0
        ):
            raise ValueError("Passing requires executed assertions and no unintended writes")
        if (self.payload_bytes is None) != (self.payload_basis == "unavailable"):
            raise ValueError("Byte count and representation must agree")
        for field in ("backend_attempts", "payload_bytes", "latency_seconds", "usage"):
            if getattr(self, field) is None and not self.unavailable.get(field, "").strip():
                raise ValueError(f"Missing {field} needs an unavailable reason")
        return self
