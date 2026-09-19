"""Wire descriptions, not a second implementation of backend business validation.

Annotated dictionaries deliberately retain unknown keys. Constraints below describe
backend contracts in JSON Schema; backend resolution remains authoritative.
"""

from typing import Annotated, Any

from pydantic import Field

APIResult = Annotated[
    dict[str, Any],
    Field(
        json_schema_extra={
            "description": "Backend response; additive fields and optional evidence are preserved.",
            "properties": {
                "error": {"description": "Backend error when the operation failed."},
                "_status_code": {"type": "integer", "description": "HTTP status on failures."},
                "_error_code": {"type": "string"},
                "_next_action": {"type": "string"},
            },
        }
    ),
]
RecipeSpecification = Annotated[
    dict,
    Field(
        json_schema_extra={
            "description": "Backend recipe envelope. api_mmm requires request; model_snapshot requires model_hash and is review-only. Unknown fields are forwarded for backend validation.",
            "properties": {
                "kind": {"type": "string", "examples": ["api_mmm", "model_snapshot"]},
                "request": {
                    "type": "object",
                    "description": "Model API request with data_source, column bindings, channels, config and optional priors.",
                },
                "model_hash": {"type": "string"},
            },
            "required": ["kind"],
        }
    ),
]
DraftSnapshot = Annotated[
    dict,
    Field(
        json_schema_extra={
            "description": "Lossless editor authoring state. Backend is authoritative; preserve unknown nested fields. Source bytes are copied into encrypted draft storage (10 MB source limit); metadata limit is 5 MB. No local filesystem paths or executable code.",
            "properties": {
                "schema_version": {"type": "integer", "enum": [1]},
                "family": {"type": "string", "enum": ["mmm", "var"]},
                "configuration": {"type": "object"},
                "model_setup": {"type": "object"},
                "model_details": {"type": "object"},
                "transformations": {"type": "object"},
                "source": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "content_base64": {"type": "string"},
                                "origin": {
                                    "type": "object",
                                    "description": "Optional uploaded dataset lineage. Backend verifies ownership and exact bytes, then supplies sha256. Retain the returned origin when reopening; it never replaces frozen source bytes.",
                                    "properties": {
                                        "kind": {"type": "string", "enum": ["uploaded_file"]},
                                        "id": {"type": "integer", "minimum": 1},
                                        "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                                    },
                                    "required": ["kind", "id"],
                                },
                            },
                            "required": ["name", "content_base64"],
                        },
                    ]
                },
            },
            "required": [
                "schema_version",
                "family",
                "configuration",
                "model_setup",
                "model_details",
                "transformations",
            ],
        }
    ),
]
QualityCheck = Annotated[
    dict,
    Field(
        json_schema_extra={
            "properties": {
                "metric": {"type": "string", "examples": ["r_hat_max", "mae", "rmse", "wape"]},
                "maximum": {
                    "type": "number",
                    "description": "Declared upper threshold: WAPE as a fraction, MAE/RMSE in outcome units, R-hat dimensionless.",
                },
                "required": {"type": "boolean", "default": True},
            },
            "required": ["metric", "maximum"],
        }
    ),
]
StudyState = Annotated[
    str,
    Field(
        description="Backend state: active, paused or archived.",
        json_schema_extra={"examples": ["active", "paused", "archived"]},
    ),
]
SubmissionKey = Annotated[
    str,
    Field(
        description="Caller-generated 8-128 character identity for one intentional attempt. Reuse identical key and inputs after a lost response; a new key may consume another attempt."
    ),
]

Channel = Annotated[
    dict,
    Field(
        json_schema_extra={
            "description": "Media channel binding. Exact activity-column keys identify channels in result/optimizer calls.",
            "properties": {
                "name": {"type": "string"},
                "activity_column": {"type": "string"},
                "spend_column": {"type": "string"},
            },
            "required": ["name", "activity_column", "spend_column"],
        }
    ),
]
ControlPrior = Annotated[
    dict,
    Field(
        json_schema_extra={
            "description": "Optional override for a selected control column. Values and priors use transformed units; discover backend support first.",
            "properties": {
                "control": {"type": "string"},
                "transform": {
                    "type": "string",
                    "examples": ["N", "DM", "STA", "DDM", "LOG"],
                    "description": "N unchanged; DM divide by variable mean; STA scale by sample SD without centering; DDM divide by variable mean within hierarchy; LOG log(x/mean(x)). Backend validates applicability.",
                },
                "distribution": {
                    "type": "string",
                    "examples": ["normal", "inversegamma", "truncatednormal", "halfnormal"],
                },
                "mean": {"type": "number"},
                "sd": {"type": "number"},
                "lower": {"type": "number"},
                "upper": {"type": "number"},
            },
            "required": ["control"],
        }
    ),
]
