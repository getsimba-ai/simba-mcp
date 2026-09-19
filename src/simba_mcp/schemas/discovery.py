"""Discovery keeps unsupported and unadvertised capabilities distinct."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CapabilityReport(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Literal["reported", "unadvertised", "unavailable"]
    source: str = "/api/v1/ingest/schema"
    advertised: dict[str, Any] = Field(
        default_factory=dict,
        description="Unmodified backend capability declarations; absent fields are unknown.",
    )
    unknown: list[str] = Field(
        default_factory=list, description="Capability categories not advertised by this backend."
    )
    guidance: str
    backend_error: dict[str, Any] | None = None
