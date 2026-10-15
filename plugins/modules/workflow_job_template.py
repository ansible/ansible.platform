#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2020, John Westcott IV <john.westcott.iv@redhat.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/workflow_job_template.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: workflow_job_template
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller workflow job templates
description:
  - Create, update, or delete workflow job templates on Ansible Automation Platform Controller.
  - Association endpoints (labels, credentials, notification_templates), survey_spec,
    copy_from, and workflow_nodes are planned for follow-up PRs.
version_added: "2.8.0"

options:
  name:
    description:
      - Name of this workflow job template.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  description:
    description:
      - Optional description of this workflow job template.
    type: str

  organization:
    description:
      - Organization name or ID the workflow job template belongs to.
    type: str

  extra_vars:
    description:
      - Variables which will be made available to jobs ran inside the workflow.
      - Accepts a YAML/JSON dictionary which will be serialized as a JSON string.
    type: dict

  survey_enabled:
    description:
      - Enable or disable the survey for this workflow job template.
    type: bool

  allow_simultaneous:
    description:
      - Allow simultaneous runs of the workflow job template.
    type: bool

  ask_variables_on_launch:
    description:
      - Prompt user for extra_vars on launch.
    type: bool

  ask_inventory_on_launch:
    description:
      - Prompt user for inventory on launch.
    type: bool

  ask_scm_branch_on_launch:
    description:
      - Prompt user for SCM branch on launch.
    type: bool

  ask_limit_on_launch:
    description:
      - Prompt user for limit on launch.
    type: bool

  ask_labels_on_launch:
    description:
      - Prompt user for labels on launch.
    type: bool

  ask_tags_on_launch:
    description:
      - Prompt user for job tags on launch.
    type: bool
    aliases:
      - ask_tags

  ask_skip_tags_on_launch:
    description:
      - Prompt user for skip tags on launch.
    type: bool

  inventory:
    description:
      - Inventory name or ID applied as a prompt, assuming the workflow prompts for inventory.
    type: str

  limit:
    description:
      - Limit applied as a prompt.
    type: str

  scm_branch:
    description:
      - SCM branch applied as a prompt.
    type: str

  job_tags:
    description:
      - Comma separated list of the tags to use for the workflow.
    type: str

  skip_tags:
    description:
      - Comma separated list of the tags to skip for the workflow.
    type: str

  webhook_service:
    description:
      - Service that webhook requests will be accepted from.
    choices: ['github', 'gitlab']
    type: str

  webhook_credential:
    description:
      - Credential name or ID for the webhook service.
    type: str

seealso:
  - module: ansible.controller.workflow_job_template
  - module: awx.awx.workflow_job_template

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Create a workflow job template
  ansible.platform.workflow_job_template:
    name: "My Workflow"
    description: "Production deployment workflow"
    organization: "Default"
    state: present

- name: Create workflow with launch prompts enabled
  ansible.platform.workflow_job_template:
    name: "Prompted Workflow"
    organization: "Default"
    ask_variables_on_launch: true
    ask_inventory_on_launch: true
    survey_enabled: false

- name: Rename a workflow job template
  ansible.platform.workflow_job_template:
    name: "My Workflow"
    new_name: "Production Workflow"
    organization: "Default"

- name: Delete a workflow job template
  ansible.platform.workflow_job_template:
    name: "Production Workflow"
    organization: "Default"
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the workflow job template was created, updated, or deleted.
  returned: always
  type: bool

workflow_job_template:
  description: >
    The workflow job template resource as it exists after the operation.
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID.
      type: int
    name:
      description: Name of the workflow job template.
      type: str
    description:
      description: Description.
      type: str
    organization:
      description: Organization ID.
      type: int
    extra_vars:
      description: Extra variables as a JSON string.
      type: str
    survey_enabled:
      description: Whether the survey is enabled.
      type: bool
    allow_simultaneous:
      description: Whether simultaneous runs are allowed.
      type: bool
...
"""
