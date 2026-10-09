#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2020, John Westcott IV <john.westcott.iv@redhat.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/schedule.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: schedule
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller schedules
description:
  - Create, update, or delete schedules on Ansible Automation Platform Controller.
  - Schedules define when a unified job template runs automatically.
  - Prompt-override fields (extra_data, inventory, credentials, etc.) are planned for a follow-up PR.
version_added: "2.8.0"

options:
  name:
    description:
      - Name of this schedule.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  description:
    description:
      - Optional description of this schedule.
    type: str

  rrule:
    description:
      - A value representing the schedule's iCal recurrence rule.
    type: str

  unified_job_template:
    description:
      - Name or ID of the unified job template to schedule.
    type: str

  enabled:
    description:
      - Enables processing of this schedule.
    type: bool

seealso:
  - module: ansible.controller.schedule
  - module: awx.awx.schedule

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Create a weekly schedule
  ansible.platform.schedule:
    name: "Weekly Demo Run"
    unified_job_template: "Demo Job Template"
    rrule: "DTSTART:20261007T120000Z RRULE:FREQ=WEEKLY;INTERVAL=1;COUNT=10"
    state: present

- name: Disable a schedule
  ansible.platform.schedule:
    name: "Weekly Demo Run"
    enabled: false

- name: Delete a schedule
  ansible.platform.schedule:
    name: "Weekly Demo Run"
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the schedule was created, updated, or deleted.
  returned: always
  type: bool

schedule:
  description: The schedule resource as it exists after the operation.
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the schedule.
      type: int
    name:
      description: Name of the schedule.
      type: str
    rrule:
      description: iCal recurrence rule string.
      type: str
    unified_job_template:
      description: Unified job template ID.
      type: int
    enabled:
      description: Whether the schedule is enabled.
      type: bool
...
"""
