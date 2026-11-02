"""Ansible License dataclass - user-facing stable interface."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AnsibleLicense:
    """Ansible representation of a Controller license configuration."""

    manifest: Optional[str] = None
    subscription_id: Optional[str] = None
    force: bool = False

    # Read-only (populated from API)
    license_info: Optional[Dict[str, Any]] = field(default=None)
