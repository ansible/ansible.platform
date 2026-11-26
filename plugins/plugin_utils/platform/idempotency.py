"""Helpers for comparing values across API and Ansible representations."""

import json
from typing import Any


def canonical_json_object(value: Any) -> Any:
    """Return one comparison form for a dict or its JSON object string."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
        if not isinstance(value, dict):
            return value

    if isinstance(value, dict):
        try:
            return json.dumps(value, sort_keys=True)
        except (TypeError, ValueError):
            return value
    return value
