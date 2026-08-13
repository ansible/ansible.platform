#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2020, John Westcott IV <john.westcott.iv@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/ad_hoc_command.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: ad_hoc_command
author: Red Hat (@RedHatOfficial)
short_description: Launch an ad hoc command
description:
  - Launch an ad hoc command on the Ansible Automation Platform controller.
  - This module always creates a new ad hoc command execution; it is not idempotent.
version_added: "3.0.0"

options:
  job_type:
    description:
      - Job type to use for the ad hoc command.
    type: str
    choices: ['run', 'check']

  inventory:
    description:
      - Inventory name, ID, or named URL to use for the ad hoc command.
    required: true
    type: str

  limit:
    description:
      - Limit to use for the ad hoc command.
    type: str

  credential:
    description:
      - Credential name, ID, or named URL to use for the ad hoc command.
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
    choices: [0, 1, 2, 3, 4, 5]

  extra_vars:
    description:
      - Extra variables to use for the ad hoc command.
    type: dict

  become_enabled:
    description:
      - If the become flag should be set.
    type: bool

  diff_mode:
    description:
      - Show the changes made by Ansible tasks where supported.
    type: bool

  execution_environment:
    description:
      - Execution Environment name, ID, or named URL to use for the ad hoc command.
    type: str

  wait:
    description:
      - Wait for the command to complete.
    default: false
    type: bool

  interval:
    description:
      - The interval in seconds to request an update from the controller.
    default: 2
    type: float

  timeout:
    description:
      - If waiting for the command to complete this will abort after this
        amount of seconds.
    type: int

extends_documentation_fragment:
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Launch an ad hoc command waiting for it to finish
  ansible.platform.ad_hoc_command:
    inventory: Demo Inventory
    credential: Demo Credential
    module_name: command
    module_args: echo I <3 Ansible
    wait: true

- name: Launch a ping command
  ansible.platform.ad_hoc_command:
    inventory: Demo Inventory
    credential: Demo Credential
    module_name: ping

- name: Launch a command with extra vars
  ansible.platform.ad_hoc_command:
    inventory: Demo Inventory
    credential: Demo Credential
    module_name: shell
    module_args: echo {{ my_var }}
    extra_vars:
      my_var: hello
    wait: true

- name: Launch a command with a specific execution environment
  ansible.platform.ad_hoc_command:
    inventory: Demo Inventory
    credential: Demo Credential
    module_name: command
    module_args: echo hello
    execution_environment: Default EE
    wait: true
...
"""

RETURN = """
id:
  description: ID of the newly launched command.
  returned: success
  type: int
  sample: 86
status:
  description: Status of the newly launched command.
  returned: success
  type: str
  sample: pending
...
"""
