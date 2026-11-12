"""Ansible model for the Controller settings singleton."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AnsibleControllerSettings:
    """User-facing representation of Controller settings."""

    settings: Optional[Dict[str, Any]] = None

    # Output fields are accepted by the shared SDK result path but are not sent
    # to the Controller API by the transform mixin.
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    changed: bool = False

    # Optional legacy single-setting input form, normalized in the SDK mixin.
    name: Optional[str] = None
    value: Optional[Any] = None
