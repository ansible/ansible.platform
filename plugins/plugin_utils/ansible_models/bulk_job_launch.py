# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AnsibleBulkJobLaunch:
    jobs: List[Dict] = field(default_factory=list)
    name: Optional[str] = None
    description: Optional[str] = None
    organization: Optional[str] = None
    inventory: Optional[str] = None
    limit: Optional[str] = None
    scm_branch: Optional[str] = None
    extra_vars: Optional[Dict] = None
    job_tags: Optional[str] = None
    skip_tags: Optional[str] = None
    wait: bool = True
    interval: float = 2.0
    timeout: Optional[int] = None
    id: Optional[int] = None
    status: Optional[str] = None
    job_info: Optional[Dict[str, Any]] = None
