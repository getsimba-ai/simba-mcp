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
            "description": "Backend recipe envelope. api_mmm requires request (a create_model body; model_type must be mmm, config.auto_prior must be false, channel_map and var_model_hash are rejected); model_snapshot requires model_hash and is review-only (launch refused, lineage unknown). Smart priors and VAR recipes are available only through the authoring-draft tools. Unknown fields are forwarded for backend validation. Every saved revision's read-time inspection carries lineage: the dataset origin recorded when the model was built, checked for availability now and never inferred after the fact.",
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
                "calibration_import": {
                    "type": "object",
                    "description": "Optional original calibration JSON reference (1 MB). Preserve separately from editable observations; backend verifies the file hash, not equivalence to current observations.",
                    "properties": {
                        "name": {"type": "string"},
                        "content_base64": {"type": "string", "maxLength": 1400000},
                        "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    },
                    "required": ["name", "content_base64"],
                },
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
                                    "description": "Optional uploaded dataset or saved pipeline-version lineage. Backend verifies ownership and exact bytes, then supplies sha256. Retain the returned origin when reopening; it never replaces frozen source bytes.",
                                    "properties": {
                                        "kind": {
                                            "type": "string",
                                            "enum": ["uploaded_file", "pipeline_version"],
                                        },
                                        "id": {"type": "integer", "minimum": 1},
                                        "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                                        "pipeline_id": {"type": "integer", "minimum": 1},
                                        "version": {"type": "integer", "minimum": 1},
                                    },
                                    "required": ["kind", "id"],
                                },
                                "history": {
                                    "type": "array",
                                    "maxItems": 100,
                                    "description": "Client-reported authoring edits. Backend validates the hash chain and final bytes, not operation semantics. Preserve when reopening. Edited sources must omit unchanged origin.",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "kind": {
                                                "type": "string",
                                                "enum": ["transform_column", "remove_column"],
                                            },
                                            "column": {"type": "string"},
                                            "output_column": {"type": "string"},
                                            "transformation": {"type": "string"},
                                            "parameter": {"type": ["number", "null"]},
                                            "input_sha256": {
                                                "type": "string",
                                                "pattern": "^[a-f0-9]{64}$",
                                            },
                                            "output_sha256": {
                                                "type": "string",
                                                "pattern": "^[a-f0-9]{64}$",
                                            },
                                            "row_count": {"type": "integer", "minimum": 0},
                                        },
                                        "required": [
                                            "kind",
                                            "column",
                                            "input_sha256",
                                            "output_sha256",
                                            "row_count",
                                        ],
                                    },
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
            "description": "Built-in metric + maximum (or operator gte/between with minimum), or custom numeric gate with metric custom:<slug>, name, units, operator and applicable bounds. Boolean/manual checks use kind, operator equals and strict boolean expected. Manual expected must be true and sign-off is session-only. Rules over saved artifacts need no external evidence: saved diagnostics (r_squared, mape, durbin_watson, pareto_k_pct, normality_p, loo_cv; bounds may be negative for loo_cv and r_squared), retained-sampling counts (retained_chains, retained_draws_per_chain, ess_bulk_min, ess_tail_min, divergences; non-negative) and provenance status (provenance:holdout, provenance:prior; operator equals, expected review_required — blocked fails, an absent record is not_collected). Every threshold is the author's; an absent artifact never passes. At least one required gate per policy; at most 20 checks in total.",
            "properties": {
                "metric": {
                    "type": "string",
                    "examples": [
                        "r_hat_max",
                        "mae",
                        "rmse",
                        "wape",
                        "prediction_mae",
                        "prediction_rmse",
                        "prediction_wape",
                        "r_squared",
                        "mape",
                        "durbin_watson",
                        "pareto_k_pct",
                        "normality_p",
                        "loo_cv",
                        "retained_chains",
                        "retained_draws_per_chain",
                        "ess_bulk_min",
                        "ess_tail_min",
                        "divergences",
                        "provenance:holdout",
                        "provenance:prior",
                        "custom:benchmark_deviation",
                    ],
                },
                "name": {"type": "string"},
                "units": {"type": "string"},
                "kind": {"type": "string", "enum": ["boolean", "manual"]},
                "expected": {"type": ["boolean", "string"]},
                "operator": {"type": "string", "enum": ["lte", "gte", "between", "equals"]},
                "minimum": {"type": "number"},
                "maximum": {"type": "number"},
                "required": {"type": "boolean", "default": True},
            },
            "required": ["metric"],
        }
    ),
]
CarryForward = Annotated[
    dict,
    Field(
        json_schema_extra={
            "description": "Reuse an earlier assessment's external evidence for the named custom metrics. Allowed only when the preview listed the metric under carry_forward_available for that assessment: same run, same evidence basis, same policy rules. Manual sign-off is never carried.",
            "properties": {
                "from_evaluation_id": {"type": "string"},
                "metrics": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^custom:[a-z][a-z0-9_]{0,63}$"},
                    "minItems": 1,
                    "maxItems": 20,
                },
            },
            "required": ["from_evaluation_id", "metrics"],
            "additionalProperties": False,
        }
    ),
]
ExternalEvidence = Annotated[
    dict,
    Field(
        json_schema_extra={
            "description": "Externally calculated numeric or strict boolean evidence; server applies policy. Manual sign-off is session-only and cannot be submitted with an API key. Source/method/digest are submitter-reported, not independently verified. Never submit a pass/fail status. To reuse an earlier submission on the same basis, use carry_forward instead of retyping.",
            "properties": {
                "metric": {"type": "string", "pattern": "^custom:[a-z][a-z0-9_]{0,63}$"},
                "value": {"type": ["number", "boolean"]},
                "method": {"type": "string", "maxLength": 5000},
                "source_reference": {"type": "string", "maxLength": 2000},
                "source_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            },
            "required": ["metric", "value", "method", "source_reference"],
            "additionalProperties": False,
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
StudyQuestion = Annotated[
    str,
    Field(
        description=(
            "What the study should find out, in one or two sentences. Stored and shown to "
            "humans; never executed or used as an acceptance rule. Do not put thresholds, "
            "validation rules or fit limits here: those belong in a quality policy, recipe "
            "revisions and max_attempts/max_concurrent. Exploratory and reliability "
            "questions are valid."
        ),
        json_schema_extra={
            "examples": [
                "How much do paid search and paid social contribute to weekly sales after price, promotions and seasonality?",
                "Which carryover and saturation choices does the data support for TV, and how sensitive are contributions to them?",
                "Can a weekly model across all channels produce estimates that hold up on a temporal holdout?",
            ]
        },
    ),
]
StudyContext = Annotated[
    str | None,
    Field(
        description=(
            "Optional scope, data caveats and assumptions a reader needs to interpret results. "
            "Not rules; see question. Omit to leave unchanged on update; send an empty string to clear."
        ),
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


ValidationProtocolSpec = Annotated[
    dict,
    Field(
        json_schema_extra={
            "description": "Declare temporal holdout before launching both models. Sampling minima describe configured intent, not retained draws or scientific certification.",
            "properties": {
                "kind": {"const": "temporal_holdout"},
                "training_end": {"type": "string", "format": "date"},
                "prediction_start": {"type": "string", "format": "date"},
                "prediction_end": {"type": "string", "format": "date"},
                "min_draws": {"type": "integer", "minimum": 1},
                "min_tune": {"type": "integer", "minimum": 1},
                "min_chains": {"type": "integer", "minimum": 2},
                "max_r_hat": {"type": "number", "minimum": 1},
                "max_prediction_wape": {"type": "number", "minimum": 0},
                "require_policy_review": {
                    "type": "boolean",
                    "description": "Require current analyst acceptance of the latest launch-policy assessment for both runs.",
                },
                "retained_sampling": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["min_ess_bulk", "min_ess_tail", "max_divergences"],
                    "properties": {
                        "min_ess_bulk": {"type": "number", "exclusiveMinimum": 0},
                        "min_ess_tail": {"type": "number", "exclusiveMinimum": 0},
                        "max_divergences": {"type": "integer", "minimum": 0},
                    },
                },
            },
            "required": [
                "training_end",
                "prediction_start",
                "prediction_end",
                "min_draws",
                "min_tune",
                "min_chains",
                "max_r_hat",
                "max_prediction_wape",
            ],
            "additionalProperties": False,
        }
    ),
]
DraftTarget = Annotated[
    dict,
    Field(
        json_schema_extra={
            "description": "The recipe an edit session works on (jellyfish #881). recipe_id must belong to the draft's study; base_revision_id, when given, must belong to that recipe (404 otherwise) and is recorded as the new revision's source. Immutable after creation: a replay naming another target is refused (409).",
            "properties": {
                "recipe_id": {"type": "string"},
                "base_revision_id": {"type": ["string", "null"]},
            },
            "required": ["recipe_id"],
            "additionalProperties": False,
        }
    ),
]
PublishTarget = Annotated[
    dict,
    Field(
        json_schema_extra={
            "description": "Publish into an existing recipe as its next revision (jellyfish #881). expected_version is the recipe version you last read; 412 stale_version when it moved, with the draft and every edit kept.",
            "properties": {
                "recipe_id": {"type": "string"},
                "expected_version": {"type": "integer", "minimum": 1},
            },
            "required": ["recipe_id", "expected_version"],
            "additionalProperties": False,
        }
    ),
]
