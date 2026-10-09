"""Ansible JobCancel dataclass - user-facing stable interface."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleJobCancel:
    """Ansible representation of a controller job cancel operation."""

    job_id: Optional[int] = None
    fail_if_not_running: bool = False

    id: Optional[int] = None
