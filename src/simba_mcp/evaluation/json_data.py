"""Strict JSON evidence decoding, independent of execution and grading."""

import json
import math


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate JSON object key")
        obj[key] = value
    return obj


def reject_constant(value):
    raise ValueError("Non-finite JSON constant")


def finite_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("Non-finite JSON float")
    return parsed


def load_json(value):
    """Preserve contradictions as parse failures, including nested objects."""
    return json.loads(
        value,
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
        parse_float=finite_float,
    )
