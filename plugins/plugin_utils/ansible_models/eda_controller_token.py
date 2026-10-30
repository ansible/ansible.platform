"""Ansible EDA Controller Token dataclass - user-facing stable interface."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleEdaControllerToken:
    """Ansible representation of an EDA controller (AWX) token."""

    # Required / identity
    name: str

    # Optional fields
    description: Optional[str] = None
    token: Optional[str] = None

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
