"""
Ansible Settings dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AnsibleSettings:
    """Ansible representation of gateway settings (bulk key-value store)."""

    # The dict of settings to apply
    settings: Optional[Dict[str, Any]] = None

    # Output fields populated after the update
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    changed: bool = False
