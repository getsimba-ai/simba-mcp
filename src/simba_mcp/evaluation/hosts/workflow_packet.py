"""Strict JSON task packets for the existing synthetic host workflow runner.

Data loading and freezing only: no provider, executor or acceptance decision.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..contracts import Case, StrictModel
from .result_selection import ResultTask

MAX_PACKET_BYTES = 16 * 1024 * 1024


class ResultWindow(StrictModel):
    start: str = ""
    end: str = ""
    granularity: Literal["", "native", "week", "month", "quarter"] = ""

    @model_validator(mode="after")
    def valid_dates(self):
        for value in (self.start, self.end):
            if value and (len(value) != 10 or date.fromisoformat(value).isoformat() != value):
                raise ValueError("Window dates must be YYYY-MM-DD")
        if self.start and self.end and self.start > self.end:
            raise ValueError("Window start must not be after end")
        return self


class ResultContract(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    required_sections: list[str] = Field(min_length=1)
    fixture: dict
    allow_prediction: bool = False
    paraphrase: str = ""
    family: str = ""
    channel: str = ""
    evidence_options: list[list[str]] = Field(default_factory=list)
    dataset: str = "packet_synthetic"
    evidence_window: ResultWindow | None = None
    section_windows: dict[str, ResultWindow] | None = None
    max_response_bytes: int | None = Field(default=None, gt=0)
    allow_recovery_errors: bool = False
    allowed_result_sections: list[str] | None = None
    forbidden_result_sections: list[str] = Field(default_factory=list)
    summary_granularity_independent: bool = False
    period_evidence_granularity: Literal["native", "month"] = "native"

    @model_validator(mode="after")
    def fixture_contract(self):
        if self.period_evidence_granularity == "month":
            from .result_period_evidence import complete_month_window

            if self.evidence_window is None or not complete_month_window(
                self.evidence_window.model_dump()
            ):
                raise ValueError("Monthly period evidence requires complete calendar months")
        if not isinstance(self.fixture.get("results"), dict):
            raise ValueError("Result fixture must supply its own results object")  # noqa: TRY004
        model_hash = self.fixture.get("model_hash")
        if not isinstance(model_hash, str) or not model_hash.strip():
            raise ValueError("Result fixture requires an explicit nonempty model_hash")
        advertised = self.fixture.get("sections_available")
        if advertised is not None and (
            not isinstance(advertised, list)
            or any(not isinstance(item, str) or not item for item in advertised)
        ):
            raise ValueError("sections_available must be a list of nonempty section names")
        for sections in [self.required_sections, *self.evidence_options]:
            if (
                not sections
                or any(not section for section in sections)
                or len(set(sections)) != len(sections)
            ):
                raise ValueError("Evidence section sets must be nonempty and unique")
        return self


class WorkflowEntry(StrictModel):
    kind: Literal["workflow"]
    family: str = ""
    prompt: str = Field(min_length=1)
    expected: dict = Field(min_length=1)
    contract: Case


class ResultEntry(StrictModel):
    kind: Literal["result"]
    prompt: str = Field(min_length=1)
    expected: dict = Field(min_length=1)
    contract: ResultContract


class PacketDocument(StrictModel):
    schema_version: int = Field(ge=1, le=1)
    packet_id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]+$")
    synthetic_only: bool
    tasks: list[Annotated[WorkflowEntry | ResultEntry, Field(discriminator="kind")]] = Field(
        min_length=1, max_length=200
    )

    @model_validator(mode="after")
    def identities(self):
        if self.synthetic_only is not True:
            raise ValueError("Packets are restricted to reviewed synthetic fixtures")
        ids = [entry.contract.id for entry in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("Packet task identifiers must be unique")
        return self


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate JSON object key in workflow packet")
        obj[key] = value
    return obj


def _reject_constant(value):
    raise ValueError("Non-finite JSON value in workflow packet")


def _finite_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("Non-finite JSON value in workflow packet")
    return parsed


def _read(path):
    with path.open("rb") as stream:
        content = stream.read(MAX_PACKET_BYTES + 1)
    if len(content) > MAX_PACKET_BYTES:
        raise ValueError("Workflow packet exceeds its byte limit")
    return content


@dataclass(frozen=True)
class WorkflowPacket:
    path: Path
    sha256: str
    document: PacketDocument

    def verify(self):
        if hashlib.sha256(_read(self.path)).hexdigest() != self.sha256:
            raise ValueError("Workflow packet changed after loading")

    def freeze(self):
        return {
            "sha256": self.sha256,
            "document": self.document.model_dump(mode="json"),
            "acceptance": False,
            "review": "External protocol and independent review required",
        }

    def triples(self):
        triples = []
        for entry in self.document.tasks:
            if isinstance(entry, WorkflowEntry):
                task = entry.contract
            else:
                fields = entry.contract.model_dump()
                for key in ("required_sections", "forbidden_result_sections"):
                    fields[key] = frozenset(fields[key])
                if fields["allowed_result_sections"] is not None:
                    fields["allowed_result_sections"] = frozenset(fields["allowed_result_sections"])
                fields["evidence_options"] = tuple(frozenset(s) for s in fields["evidence_options"])
                task = ResultTask(prompt=entry.prompt, expected=entry.expected, **fields)
            triples.append((task, entry.prompt, entry.expected))
        return triples


def load_workflow_packet(path):
    path = Path(path).resolve()
    raw = _read(path)
    data = json.loads(
        raw,
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
        parse_float=_finite_float,
    )
    document = PacketDocument.model_validate(data)
    return WorkflowPacket(path, hashlib.sha256(raw).hexdigest(), document)
