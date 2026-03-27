"""
Ansible CA Certificate dataclass - user-facing stable interface.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleCACertificate:
    """Ansible representation of a CA certificate."""

    name: str
    pem_data: Optional[str] = None
    sha256: Optional[str] = None
    related_id_reference: Optional[str] = None
    state: str = "present"

    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
