#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/ad_hoc_command_cancel.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: ad_hoc_command_cancel
author: Red Hat (@RedHatOfficial)
short_description: Cancel a Controller ad hoc command.
description:
  - Cancel an ad hoc command on Ansible Automation Platform Controller.
  - If the command has already finished, the module returns successfully with no changes.
version_added: "2.8.0"

options:
  command_id:
    description:
      - ID of the ad hoc command to cancel.
    required: true
    type: int

  fail_if_not_running:
    description:
      - Fail loudly if the command cannot be canceled (already finished).
    default: false
    type: bool

extends_documentation_fragment:
  - ansible.platform.auth

seealso:
  - module: ansible.controller.ad_hoc_command_cancel
  - module: awx.awx.ad_hoc_command_cancel
  - module: ansible.platform.ad_hoc_command
...
"""

EXAMPLES = """
- name: Cancel a running ad hoc command
  ansible.platform.ad_hoc_command_cancel:
    command_id: 123

- name: Cancel a command and fail if it is not running
  ansible.platform.ad_hoc_command_cancel:
    command_id: 456
    fail_if_not_running: true
...
"""

RETURN = """
id:
  description: The ID of the command that was requested to be canceled.
  returned: success
  type: int
  sample: 123

changed:
  description: Whether the command was actually canceled (false if already finished).
  returned: always
  type: bool

status:
  description: A short status message describing the cancel outcome.
  returned: success
  type: str
  sample: "canceled"
...
"""
