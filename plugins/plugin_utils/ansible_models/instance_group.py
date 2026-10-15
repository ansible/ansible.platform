"""
Ansible InstanceGroup dataclass - user-facing stable interface.

This dataclass represents the instance group as seen by Ansible playbooks.
Field names and types remain stable across API versions.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class AnsibleInstanceGroup:
    """Ansible representation of a Controller instance group."""

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    credential: Optional[str] = None
    is_container_group: Optional[bool] = None
    policy_instance_percentage: Optional[int] = None
    policy_instance_minimum: Optional[int] = None
    max_concurrent_jobs: Optional[int] = None
    max_forks: Optional[int] = None
    policy_instance_list: Optional[List[Any]] = None
    pod_spec_override: Optional[str] = None
    state: str = "present"

    # Association fields (not sent to API directly, handled by action plugin)
    instances: Optional[List[str]] = field(default=None)

    # Read-only fields (populated from API responses)
    id: Optional[int] = None
