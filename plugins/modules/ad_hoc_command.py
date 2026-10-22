#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/ad_hoc_command.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: ad_hoc_command
author: Red Hat (@RedHatOfficial)
short_description: Launch a Controller ad hoc command
description:
  - Launch an ad hoc command on Ansible Automation Platform Controller.
  - Every invocation launches a new command; this module is not idempotent.
  - Optionally waits for the command to complete and reports its final status.
version_added: "2.8.0"

options:
  job_type:
    description:
      - Job type to use for the ad hoc command.
    type: str
    choices:
      - run
      - check

  inventory:
    description:
      - Inventory name or ID to use for the ad hoc command.
    required: true
    type: str

  limit:
    description:
      - Limit to use for the ad hoc command.
    type: str

  credential:
    description:
      - Credential name or ID to use for the ad hoc command.
    required: true
    type: str

  module_name:
    description:
      - The Ansible module to execute.
    required: true
    type: str

  module_args:
    description:
      - The arguments to pass to the module.
    type: str

  forks:
    description:
      - The number of forks to use for this ad hoc execution.
    type: int

  verbosity:
    description:
      - Verbosity level for this ad hoc command run.
    type: int
    choices:
      - 0
      - 1
      - 2
      - 3
      - 4
      - 5

  extra_vars:
    description:
      - Extra variables to use for the ad hoc command.
    type: dict

  become_enabled:
    description:
      - Whether the become flag should be set.
    type: bool

  diff_mode:
    description:
      - Show the changes made by Ansible tasks where supported.
    type: bool

  execution_environment:
    description:
      - Execution Environment name or ID to use for the ad hoc command.
    type: str

  wait:
    description:
      - Wait for the command to complete.
    default: false
    type: bool

  interval:
    description:
      - Polling interval in seconds when waiting.
    default: 2.0
    type: float

  timeout:
    description:
      - Maximum seconds to wait before aborting (client-side).
      - Only used when C(wait=true).
    type: int

seealso:
  - module: ansible.controller.ad_hoc_command
  - module: awx.awx.ad_hoc_command

extends_documentation_fragment:
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Launch an ad hoc command waiting for it to finish
  ansible.platform.ad_hoc_command:
    inventory: "Demo Inventory"
    credential: "Demo Credential"
    module_name: command
    module_args: echo hello
    wait: true

- name: Launch an ad hoc command without waiting
  ansible.platform.ad_hoc_command:
    inventory: "Demo Inventory"
    credential: "Demo Credential"
    module_name: ping
    wait: false

- name: Run a command with privilege escalation
  ansible.platform.ad_hoc_command:
    inventory: "Demo Inventory"
    credential: "Demo Credential"
    module_name: command
    module_args: whoami
    become_enabled: true
    verbosity: 2
    wait: true
    timeout: 120
...
"""

RETURN = """
id:
  description: ID of the launched ad hoc command.
  returned: success
  type: int
  sample: 86

status:
  description: Status of the ad hoc command.
  returned: success
  type: str
  sample: pending
...
"""
