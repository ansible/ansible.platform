"""
Ansible ProjectUpdate dataclass - user-facing stable interface.

This dataclass represents a project update (sync) launch request as seen by
Ansible playbooks. The wait/interval/timeout parameters control polling in
PlatformService/DirectHTTPClient.execute() (platform_manager.py,
direct_client.py) — they are popped from the ansible_data dict before this
dataclass is constructed, so they are not fields here.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleProjectUpdate:
    """Ansible representation of a project update launch request."""

    name: str

    # Read-only fields from API response (of the launched project_update job)
    id: Optional[int] = None
    status: Optional[str] = None
    finished: Optional[str] = None
