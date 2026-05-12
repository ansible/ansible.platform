"""
Ansible FeatureFlag dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AnsibleFeatureFlag:
    """Ansible representation of a gateway feature flag."""

    # Required
    name: str

    # Writable fields
    value: Optional[str] = None

    state: str = "exists"

    # Read-only fields (returned by API)
    id: Optional[int] = None
    ui_name: Optional[str] = None
    condition: Optional[str] = None
    required: Optional[bool] = None
    support_level: Optional[str] = None
    visibility: Optional[bool] = None
    toggle_type: Optional[str] = None
    description: Optional[str] = None
    support_url: Optional[str] = None
    labels: Optional[List[str]] = None
