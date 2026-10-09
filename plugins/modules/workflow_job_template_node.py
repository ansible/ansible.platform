#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2020, John Westcott IV <john.westcott.iv@redhat.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/workflow_job_template_node.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: workflow_job_template_node
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller workflow job template nodes
description:
  - Create, update, or delete workflow job template nodes on Ansible Automation Platform Controller.
  - Nodes define the steps within a workflow job template graph.
  - Prompt-override fields, node relationships (success/failure/always), credentials,
    labels, and approval nodes are planned for a follow-up PR.
version_added: "2.8.0"

options:
  identifier:
    description:
      - An identifier for this node that is unique within its workflow.
      - It is copied to workflow job nodes corresponding to this node.
    required: true
    type: str

  workflow_job_template:
    description:
      - The workflow job template name or ID that this node belongs to.
    required: true
    type: str
    aliases:
      - workflow

  unified_job_template:
    description:
      - Name or ID of the unified job template to run in this workflow node.
      - Can be a job template, project, inventory source, etc.
    type: str

  all_parents_must_converge:
    description:
      - If enabled then the node will only run if all of the parent nodes
        have met the criteria to reach this node.
    type: bool

seealso:
  - module: ansible.controller.workflow_job_template_node
  - module: awx.awx.workflow_job_template_node

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Create a workflow node
  ansible.platform.workflow_job_template_node:
    identifier: node_101
    workflow_job_template: "My Workflow"
    unified_job_template: "Demo Job Template"
    all_parents_must_converge: false
    state: present

- name: Delete a workflow node
  ansible.platform.workflow_job_template_node:
    identifier: node_101
    workflow_job_template: "My Workflow"
    state: absent

- name: Check whether a node exists
  ansible.platform.workflow_job_template_node:
    identifier: node_101
    workflow_job_template: "My Workflow"
    state: exists
  register: node_check
...
"""

RETURN = """
changed:
  description: Whether the node was created, updated, or deleted.
  returned: always
  type: bool

workflow_job_template_node:
  description: >
    The workflow job template node resource as it exists after the operation.
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the node.
      type: int
    identifier:
      description: Unique identifier for this node within its workflow.
      type: str
    workflow_job_template:
      description: Workflow job template this node belongs to (ID).
      type: int
    unified_job_template:
      description: The unified job template this node runs (ID).
      type: int
    all_parents_must_converge:
      description: Whether all parent nodes must succeed before this node runs.
      type: bool
...
"""
