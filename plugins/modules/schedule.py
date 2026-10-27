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
  - Supports prompt-override fields for launch-time configuration.
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

  extra_data:
    description:
      - Extra variables for the scheduled launch.
    type: dict

  inventory:
    description:
      - Inventory name or ID to use for the scheduled launch.
    type: str

  scm_branch:
    description:
      - SCM branch to use for the scheduled launch.
    type: str

  job_type:
    description:
      - Job type to use for the scheduled launch.
    choices: ['run', 'check']
    type: str

  job_tags:
    description:
      - Job tags for the scheduled launch.
    type: str

  skip_tags:
    description:
      - Tags to skip for the scheduled launch.
    type: str

  limit:
    description:
      - Host limit for the scheduled launch.
    type: str

  diff_mode:
    description:
      - Show changes for the scheduled launch.
    type: bool

  verbosity:
    description:
      - Verbosity level for the scheduled launch.
    choices: [0, 1, 2, 3, 4, 5]
    type: int

  forks:
    description:
      - Number of forks for the scheduled launch.
    type: int

  job_slice_count:
    description:
      - Job slice count for the scheduled launch.
    type: int

  timeout:
    description:
      - Timeout in seconds for the scheduled launch.
    type: int

  execution_environment:
    description:
      - Execution environment name or ID for the scheduled launch.
    type: str

  credentials:
    description:
      - List of credential names or IDs to associate with this schedule.
    type: list
    elements: str

  labels:
    description:
      - List of label names or IDs to associate with this schedule.
    type: list
    elements: str

  instance_groups:
    description:
      - List of instance group names or IDs to associate with this schedule.
    type: list
    elements: str

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
      type: str
    enabled:
      description: Whether the schedule is enabled.
      type: bool
...
"""
