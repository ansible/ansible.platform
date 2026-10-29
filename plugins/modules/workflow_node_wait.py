#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: workflow_node_wait
author: "Red Hat (@RedHatOfficial)"
short_description: Wait for a workflow node to finish.
description:
    - Wait for a specific workflow node within a workflow job to appear and
      reach a terminal status.
    - Polls the workflow job's nodes until a node matching the given C(name)
      appears, then polls the underlying job until it finishes.
options:
    workflow_job_id:
        description:
            - ID of the workflow job to monitor for the node.
        required: true
        type: int
    name:
        description:
            - Name of the workflow node's job to wait for.
        required: true
        type: str
    interval:
        description:
            - Interval in seconds between polling requests.
        default: 1
        type: float
    timeout:
        description:
            - Maximum time in seconds to wait for the workflow node to finish.
            - Set to C(0) to wait indefinitely.
        default: 10
        type: int
seealso:
    - module: ansible.controller.workflow_node_wait
    - module: awx.awx.workflow_node_wait
extends_documentation_fragment: ansible.platform.auth
version_added: "2.8.0"
"""

EXAMPLES = """
- name: Launch a workflow without waiting
  ansible.platform.workflow_launch:
    name: "Test Workflow"
    wait: false
  register: workflow

- name: Wait for a specific workflow node to finish
  ansible.platform.workflow_node_wait:
    workflow_job_id: "{{ workflow.id }}"
    name: "Approval Data Step"
    timeout: 120
    interval: 2
...
"""

RETURN = """
id:
    description: ID of the workflow node's job.
    returned: success
    type: int
    sample: 42
status:
    description: Final status of the workflow node's job.
    returned: success
    type: str
    sample: successful
elapsed:
    description: Elapsed time of the workflow node's job in seconds.
    returned: success
    type: float
    sample: 12.5
job_data:
    description: Full response from the workflow node's job API.
    returned: success
    type: dict
...
"""
