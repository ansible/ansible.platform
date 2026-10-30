"""Ansible Rulebook Activation Copy dataclass - user-facing stable interface."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleRulebookActivationCopy:
    """Ansible representation of an EDA rulebook activation copy operation."""

    # Required fields
    name: str
    copy_from: Optional[str] = None

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
