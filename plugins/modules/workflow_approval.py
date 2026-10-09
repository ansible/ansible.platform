#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: workflow_approval
author: "Ansible Platform Collection Contributors"
short_description: Approve or deny a pending workflow approval node.
description:
    - Wait for an approval node in a workflow job to reach a pending state,
      then approve or deny it.
    - This module polls the workflow job's nodes endpoint until the named
      approval node appears, then takes the requested action.
options:
    workflow_job_id:
      description:
        - ID of the workflow job to monitor for an approval node.
      required: True
      type: int
    name:
      description:
        - Name of the approval node to approve or deny.
      required: True
      type: str
    action:
      description:
        - Whether to approve or deny the approval node.
      choices: ["approve", "deny"]
      default: "approve"
      type: str
    interval:
      description:
        - Seconds between poll requests when waiting for the approval node.
      required: False
      default: 1
      type: float
    timeout:
      description:
        - Maximum seconds to wait for the approval node to appear.
      default: 10
      type: int
seealso:
    - module: ansible.controller.workflow_approval
    - module: awx.awx.workflow_approval
extends_documentation_fragment: ansible.platform.auth
"""

EXAMPLES = """
- name: Launch a workflow and register the job
  ansible.platform.workflow_launch:
    workflow_template: "Test Workflow"
    wait: false
  register: workflow

- name: Wait for approval node and approve it
  ansible.platform.workflow_approval:
    workflow_job_id: "{{ workflow.id }}"
    name: approval_jt_name
    interval: 5
    timeout: 60
    action: approve

- name: Wait for approval node and deny it
  ansible.platform.workflow_approval:
    workflow_job_id: "{{ workflow.id }}"
    name: approval_jt_name
    interval: 5
    timeout: 30
    action: deny
"""

RETURN = """
workflow_job_id:
  description: The workflow job ID that was monitored.
  type: int
  returned: always
node_name:
  description: The name of the approval node acted on.
  type: str
  returned: success
action:
  description: The action taken (approve or deny).
  type: str
  returned: success
approval_node_id:
  description: The ID of the workflow node that was found.
  type: int
  returned: success
"""
