"""
Ansible AdHocCommand dataclass - user-facing stable interface.

This dataclass represents the ad hoc command parameters as seen by Ansible playbooks.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleAdHocCommand:
    """
    Ansible representation of an ad hoc command launch request.

    Fields match the DOCUMENTATION options that are sent to the API.
    The wait/interval/timeout parameters are handled by the action plugin
    and are not included here.
    """

    inventory: str
    credential: str
    module_name: str
    job_type: Optional[str] = None
    limit: Optional[str] = None
    module_args: Optional[str] = None
    forks: Optional[int] = None
    verbosity: Optional[int] = None
    extra_vars: Optional[dict] = None
    become_enabled: Optional[bool] = None
    diff_mode: Optional[bool] = None
    execution_environment: Optional[str] = None

    # Read-only fields from API response
    id: Optional[int] = None
    status: Optional[str] = None
    finished: Optional[str] = None
    event_processing_finished: Optional[bool] = None
