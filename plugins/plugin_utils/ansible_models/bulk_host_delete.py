# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import dataclass, field
from typing import List


@dataclass
class AnsibleBulkHostDelete:
    hosts: List[int] = field(default_factory=list)
