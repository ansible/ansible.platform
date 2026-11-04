"""Canonicalize API payloads used by idempotent sub-resource reconciliation."""

from __future__ import annotations

from typing import Any

# Controller may include server metadata in singleton responses. These fields
# are not part of the user-facing survey specification.
_SURVEY_METADATA_FIELDS = frozenset({"id", "url", "created", "modified", "related", "summary_fields", "resource_uri"})
_SURVEY_TOP_LEVEL_ORDER = ("name", "description", "spec")
_SURVEY_QUESTION_ORDER = (
    "question_name",
    "question_description",
    "type",
    "variable",
    "required",
    "default",
    "choices",
    "min",
    "max",
    "new_question",
)


def _canonicalize_mapping(value: dict, preferred_order: tuple[str, ...] = ()) -> dict:
    """Return a recursively canonicalized mapping with stable key order."""
    result = {}
    preferred = set(preferred_order)

    for key in preferred_order:
        if key in value and key not in _SURVEY_METADATA_FIELDS:
            result[key] = _canonicalize_value(value[key])

    for key in sorted(value):
        if key in preferred or key in _SURVEY_METADATA_FIELDS:
            continue
        result[key] = _canonicalize_value(value[key])

    return result


def _canonicalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _canonicalize_mapping(value)
    if isinstance(value, list):
        return [_canonicalize_value(item) for item in value]
    return value


def canonicalize_survey_spec(value: Any) -> Any:
    """Normalize a Controller survey response for stable idempotency checks.

    Survey question order is meaningful and is preserved. Mapping keys are
    emitted in a stable order, while API-only metadata is removed from the
    comparison payload.
    """
    if not isinstance(value, dict):
        return value

    normalized = {}
    for key in _SURVEY_TOP_LEVEL_ORDER:
        if key in value:
            if key == "spec" and isinstance(value[key], list):
                normalized[key] = [
                    _canonicalize_mapping(question, _SURVEY_QUESTION_ORDER) if isinstance(question, dict) else _canonicalize_value(question)
                    for question in value[key]
                ]
            else:
                normalized[key] = _canonicalize_value(value[key])

    for key in sorted(value):
        if key in _SURVEY_TOP_LEVEL_ORDER or key in _SURVEY_METADATA_FIELDS:
            continue
        normalized[key] = _canonicalize_value(value[key])

    return normalized


def canonicalize_sub_resource(sub_path: str, value: Any) -> Any:
    """Canonicalize a supported singleton sub-resource payload."""
    if sub_path == "survey_spec":
        return canonicalize_survey_spec(value)
    return value
