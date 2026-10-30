#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2025, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/workflow_launch.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: workflow_launch
author: Red Hat (@RedHatOfficial)
short_description: Launch an Automation Controller workflow job template.
description:
  - Launch a workflow job template on Ansible Automation Platform Controller.
  - This module is non-idempotent; every invocation creates a new workflow job.
  - Optionally waits for the workflow job to complete before returning.
version_added: "2.8.0"

options:
  name:
    description:
      - The name of the workflow job template to launch.
    required: true
    type: str
    aliases:
      - workflow_template

  organization:
    description:
      - Organization name or ID the workflow job template exists in.
      - Used to disambiguate when multiple workflow job templates share the same name.
    type: str

  inventory:
    description:
      - Inventory name or ID to use for the workflow job.
      - Only used if the workflow job template has I(ask_inventory_on_launch) enabled.
    type: str

  limit:
    description:
      - Host limit to apply to the workflow job.
      - Only used if the workflow job template has I(ask_limit_on_launch) enabled.
    type: str

  tags:
    description:
      - Specific tags to use for the workflow job.
      - Only used if the workflow job template has I(ask_tags_on_launch) enabled.
    type: list
    elements: str

  skip_tags:
    description:
      - Specific tags to skip for the workflow job.
      - Only used if the workflow job template has I(ask_skip_tags_on_launch) enabled.
    type: list
    elements: str

  scm_branch:
    description:
      - A specific branch of the SCM project to run the template on.
      - Only applicable if the project allows for branch override.
      - Only used if the workflow job template has I(ask_scm_branch_on_launch) enabled.
    type: str

  extra_vars:
    description:
      - Extra variables to pass to the workflow job.
      - Only used if the workflow job template has I(ask_variables_on_launch) or
        I(survey_enabled) set.
    type: dict

  wait:
    description:
      - Wait for the workflow job to complete.
    default: true
    type: bool

  interval:
    description:
      - Polling interval in seconds when waiting for the workflow job to complete.
    default: 2
    type: float

  timeout:
    description:
      - Maximum time in seconds to wait for the workflow job to complete.
      - If not set, waits indefinitely, matching the legacy module behavior.
    type: int

seealso:
  - module: ansible.controller.workflow_launch
  - module: awx.awx.workflow_launch

extends_documentation_fragment:
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Launch a workflow with a timeout of 10 seconds
  ansible.platform.workflow_launch:
    name: "Test Workflow"
    timeout: 10

- name: Launch a workflow with extra_vars without waiting
  ansible.platform.workflow_launch:
    name: "Test Workflow"
    extra_vars:
      var1: My First Variable
      var2: My Second Variable
    wait: false

- name: Launch a workflow in a specific organization
  ansible.platform.workflow_launch:
    name: "Deploy Pipeline"
    organization: "Production"
    inventory: "Production Servers"
    limit: "webservers"

- name: Launch a workflow using the legacy alias
  ansible.platform.workflow_launch:
    workflow_template: "Test Workflow"
    wait: true
...
"""

RETURN = """
changed:
  description: Whether a workflow job was launched (always true on success).
  returned: always
  type: bool

id:
  description: The ID of the launched workflow job.
  returned: success
  type: int
  sample: 42

status:
  description: The final status of the workflow job.
  returned: success
  type: str
  sample: "successful"

workflow_launch:
  description: The workflow job resource.
  returned: success
  type: dict
  contains:
    id:
      description: Numeric ID of the launched workflow job.
      type: int
    status:
      description: Status of the workflow job.
      type: str

job_info:
  description: Backward-compatible information about the launched workflow job.
  returned: success
  type: dict
  contains:
    id:
      description: Numeric ID of the launched workflow job.
      type: int
...
"""
