"""
Ansible InventorySourceUpdate dataclass - user-facing stable interface.

This dataclass represents an inventory source update (sync) launch request as
seen by Ansible playbooks. Fields match the DOCUMENTATION options that are
sent to the API. The wait/interval/timeout parameters control polling in
PlatformService/DirectHTTPClient.execute() (platform_manager.py,
direct_client.py) — they are popped from the ansible_data dict before this
dataclass is constructed, so they are not fields here.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleInventorySourceUpdate:
    """Ansible representation of an inventory source update launch request."""

    name: str
    inventory: Optional[str] = None

    # Read-only fields from API response (of the launched inventory_update job)
    id: Optional[int] = None
    status: Optional[str] = None
    finished: Optional[str] = None
