# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleWorkflowNodeWait:
    workflow_job_id: int = 0
    name: str = ""
    interval: float = 1.0
    timeout: Optional[int] = 10
