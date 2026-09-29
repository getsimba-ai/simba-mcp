"""Versioned evaluation data contracts, independent of execution and presentation."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Exchange(StrictModel):
    method: Literal["GET", "POST", "PATCH", "DELETE"]
    path: str
    query: dict[str, str] = Field(default_factory=dict)
    body: dict | None = None
    status: int = Field(default=200, ge=100, le=599)
    response: dict = Field(default_factory=dict)
    fault: Literal["timeout", "cancel"] | None = None


class Step(StrictModel):
    tool: str
    arguments: dict
    exchanges: list[Exchange]
    expected: dict
    is_error: bool = False
    cancelled: bool = False
    tool_error: str | None = None

    @model_validator(mode="after")
    def validate_outcome(self):
        if self.cancelled and (self.tool_error or self.is_error or self.expected):
            raise ValueError("Cancellation must have a single explicit outcome")
        if not self.cancelled and not self.tool_error and not self.expected:
            raise ValueError("A result requires independent expected fields")
        if self.tool_error and not self.is_error:
            raise ValueError("A tool exception is an error")
        return self


class Case(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    purpose: str = Field(min_length=1)
    steps: list[Step] = Field(min_length=1)


class Trial(StrictModel):
    case_id: str
    repetition: int = Field(ge=0)
    passed: bool
    assertions: dict[str, bool]
    unintended_writes: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    backend_attempts: int = Field(ge=0)
    latency_seconds: float = Field(ge=0, allow_inf_nan=False)
    content_json_bytes: int = Field(ge=0)
    call_tool_result_json_bytes: int = Field(ge=0)
    backend_decoded_bytes: int = Field(ge=0)
    backend_downloaded_bytes: int = Field(ge=0)
    # These cannot be observed by this scripted, in-process command.
    model_turns: None = None
    provider_usage: None = None
    mcp_transport_bytes: None = None
    unavailable_reason: Literal["scripted_in_process"] = "scripted_in_process"

    @model_validator(mode="after")
    def check_verdict(self):
        if not self.assertions or self.passed != all(self.assertions.values()):
            raise ValueError("Verdict must match nonempty assertion results")
        if self.passed and self.unintended_writes:
            raise ValueError("Unintended writes cannot pass")
        return self


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
