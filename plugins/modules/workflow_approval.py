#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/workflow_approval.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: workflow_approval
author: Red Hat (@RedHatOfficial)
short_description: Approve or deny a workflow approval node
description:
  - Approve or deny an approval node in a controller workflow job.
  - Waits for the specified approval node to become pending before taking action.
  - This module targets the Controller API through the platform gateway.
version_added: "1.0.0"

options:
  workflow_job_id:
    description:
      - ID of the workflow job to monitor for approval.
    required: true
    type: int

  name:
    description:
      - Name of the approval node to approve or deny.
    required: true
    type: str

  action:
    description:
      - Type of action to take on the approval node.
    choices: ["approve", "deny"]
    default: "approve"
    type: str

  interval:
    description:
      - The interval in seconds to request an update from the controller.
    required: false
    default: 1
    type: float

  timeout:
    description:
      - Maximum time in seconds to wait for the workflow job to reach the approval node.
    default: 10
    type: int

extends_documentation_fragment:
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Launch a workflow and register the result
  ansible.platform.controller_workflow_launch:
    workflow_template: "Test Workflow"
    wait: false
  register: workflow

- name: Wait for approval node and approve
  ansible.platform.workflow_approval:
    workflow_job_id: "{{ workflow.id }}"
    name: approval_jt_name
    interval: 5
    timeout: 30
    action: approve

- name: Wait for approval node and deny
  ansible.platform.workflow_approval:
    workflow_job_id: "{{ workflow.id }}"
    name: approval_jt_name
    interval: 5
    timeout: 30
    action: deny
"""

RETURN = """
changed:
  description: Whether the approval node was approved or denied.
  returned: always
  type: bool

msg:
  description: Human-readable result message.
  returned: always
  type: str
"""
