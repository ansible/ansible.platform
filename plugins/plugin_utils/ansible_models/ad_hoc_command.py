"""Ansible model for Controller ad hoc command launches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union


@dataclass
class AnsibleAdHocCommand:
    """Stable Ansible representation of ad hoc command inputs and results."""

    inventory: Optional[str] = None
    credential: Optional[str] = None
    execution_environment: Optional[str] = None
    module_name: Optional[str] = None
    module_args: Optional[str] = None
    job_type: Optional[str] = None
    limit: Optional[str] = None
    forks: Optional[int] = None
    verbosity: Optional[int] = None
    extra_vars: Optional[Union[Dict[str, Any], str]] = None
    become_enabled: Optional[bool] = None
    diff_mode: Optional[bool] = None
    wait: bool = False
    interval: float = 2.0
    timeout: Optional[int] = None
    id: Optional[int] = None
    status: Optional[str] = None
