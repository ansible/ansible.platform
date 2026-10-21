"""Ansible AdHocCommandCancel dataclass - user-facing stable interface."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleAdHocCommandCancel:
    """Ansible representation of an ad hoc command cancel request."""

    command_id: int = 0
    fail_if_not_running: bool = False
    id: Optional[int] = None
