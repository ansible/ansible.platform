#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: ad_hoc_command_wait
author: Red Hat (@RedHatOfficial)
short_description: Wait for a Controller ad hoc command to finish.
description:
    - Wait for a Controller ad hoc command to reach a terminal status and report success or failure.
    - This module is read-only and never modifies the ad hoc command.
options:
    command_id:
        description:
            - ID of the ad hoc command to wait on.
        required: true
        type: int
    interval:
        description:
            - The interval in seconds between polling requests to the controller.
        required: false
        default: 2
        type: float
    timeout:
        description:
            - Maximum time in seconds to wait for the ad hoc command to finish.
            - If omitted or set to C(0), wait indefinitely.
            - Negative values are not allowed.
        required: false
        type: int
seealso:
    - module: ansible.controller.ad_hoc_command_wait
    - module: awx.awx.ad_hoc_command_wait
extends_documentation_fragment: ansible.platform.auth
version_added: "2.8.0"
"""

EXAMPLES = """
- name: Launch an ad hoc command
  ansible.platform.ad_hoc_command:
    inventory: "Demo Inventory"
    credential: "Demo Credential"
    module_name: ping
    wait: false
  register: command

- name: Wait for ad hoc command max 120s
  ansible.platform.ad_hoc_command_wait:
    command_id: "{{ command.id }}"
    timeout: 120

- name: Wait for ad hoc command with custom poll interval
  ansible.platform.ad_hoc_command_wait:
    command_id: "{{ command.id }}"
    interval: 5
    timeout: 300
...
"""

RETURN = """
id:
    description: Ad hoc command ID that was waited on.
    returned: success
    type: int
    sample: 99
elapsed:
    description: Total time in seconds the command took to run.
    returned: success
    type: float
    sample: 10.879
started:
    description: Timestamp of when the command started running.
    returned: success
    type: str
    sample: "2017-03-01T17:03:53.200234Z"
finished:
    description: Timestamp of when the command finished running.
    returned: success
    type: str
    sample: "2017-03-01T17:04:04.078782Z"
status:
    description: Final status of the ad hoc command.
    returned: success
    type: str
    sample: successful
...
"""
