"""
Ansible JobCancel dataclass - user-facing stable interface.
"""

from dataclasses import dataclass


@dataclass
class AnsibleJobCancel:
    """
    Ansible representation of a job cancel operation.
    """

    job_id: int = 0
    fail_if_not_running: bool = False
