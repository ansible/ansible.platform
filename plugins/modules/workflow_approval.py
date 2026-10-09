#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


DOCUMENTATION = """
---
module: workflow_approval
author: "Sean Sullivan (@sean-m-sullivan)"
short_description: Approve or deny a pending workflow approval node.
description:
    - Approve or deny an approval node in a workflow job.
    - This module polls a running workflow job for a named approval node.
      Once the node reaches the pending state, the specified action
      (approve or deny) is executed.
options:
    workflow_job_id:
      description:
        - ID of the workflow job to monitor for approval.
      required: True
      type: int
    name:
      description:
        - Name of the approval node to approve or deny.
      required: True
      type: str
    action:
      description:
        - Type of action to take.
      choices: ["approve", "deny"]
      default: "approve"
      type: str
    interval:
      description:
        - The interval in seconds to request an update from the controller.
      required: False
      default: 1
      type: float
    timeout:
      description:
        - Maximum time in seconds to wait for a workflow job to reach approval node.
      default: 10
      type: int

extends_documentation_fragment: ansible.platform.auth
"""


EXAMPLES = """
- name: Create a workflow approval node
  ansible.platform.workflow_job_template_node:
    identifier: approval_test
    approval_node:
      name: approval_jt_name
      timeout: 900
    workflow: "Test Workflow"

- name: Launch the workflow with a timeout of 10 seconds
  ansible.platform.workflow_launch:
    workflow_template: "Test Workflow"
    wait: false
  register: workflow

- name: Wait for approval node to activate and approve
  ansible.platform.workflow_approval:
    workflow_job_id: "{{ workflow.id }}"
    name: approval_jt_name
    interval: 10
    timeout: 20
    action: approve

- name: Wait for approval node to activate and deny
  ansible.platform.workflow_approval:
    workflow_job_id: "{{ workflow.id }}"
    name: approval_jt_name
    interval: 10
    timeout: 20
    action: deny
"""

RETURN = """
workflow_approval:
  type: dict
  description: Result of the workflow approval action.
  returned: success
  contains:
    workflow_job_id:
      description: The workflow job ID that was monitored.
      type: int
    name:
      description: The name of the approval node.
      type: str
    action:
      description: The action that was taken (approve or deny).
      type: str
    approval_id:
      description: The ID of the workflow approval that was acted upon.
      type: int
"""
