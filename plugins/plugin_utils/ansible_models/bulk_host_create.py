"""
Ansible BulkHostCreate dataclass - user-facing stable interface.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AnsibleBulkHostCreate:
    """
    Ansible representation of a bulk host create operation.
    """

    hosts: List = field(default_factory=list)
    inventory: Optional[str] = None
