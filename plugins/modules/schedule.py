#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2020, John Westcott IV <john.westcott.iv@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/schedule.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: schedule
author: Red Hat (@RedHatOfficial)
short_description: Create, update, or destroy Automation Platform Controller schedules
description:
  - Create, update, or destroy Automation Platform Controller schedules.
version_added: "3.0.0"

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
      - Required when creating a new schedule.
    type: str

  unified_job_template:
    description:
      - Name, ID, or named URL of unified job template to schedule.
      - Used to look up an already existing schedule, and required when creating a new one.
    type: str

  execution_environment:
    description:
      - Execution Environment name, ID, or named URL applied as a prompt, assuming the job template prompts for execution environment.
    type: str

  extra_data:
    description:
      - Specify C(extra_vars) for the template.
    type: dict

  forks:
    description:
      - Forks applied as a prompt, assuming the job template prompts for forks.
    type: int

  instance_groups:
    description:
      - List of Instance Group names, IDs, or named URLs applied as a prompt, assuming the job template prompts for instance groups.
    type: list
    elements: str

  inventory:
    description:
      - Inventory name, ID, or named URL applied as a prompt, assuming the job template prompts for inventory.
    type: str

  job_slice_count:
    description:
      - Job Slice Count applied as a prompt, assuming the job template prompts for job slice count.
    type: int

  labels:
    description:
      - List of label names applied as a prompt, assuming the job template prompts for labels.
    type: list
    elements: str

  credentials:
    description:
      - List of credential names, IDs, or named URLs applied as a prompt, assuming the job template prompts for credentials.
    type: list
    elements: str

  scm_branch:
    description:
      - Branch to use in the job run. Project default used if blank. Only allowed if the project's C(allow_override) field is set to true.
    type: str

  timeout:
    description:
      - Timeout applied as a prompt, assuming the job template prompts for timeout.
    type: int

  job_type:
    description:
      - The job type to use for the job template.
    type: str
    choices: ['run', 'check']

  job_tags:
    description:
      - Comma separated list of the tags to use for the job template.
    type: str

  skip_tags:
    description:
      - Comma separated list of the tags to skip for the job template.
    type: str

  limit:
    description:
      - A host pattern to further constrain the list of hosts managed or affected by the playbook.
    type: str

  diff_mode:
    description:
      - Enable diff mode for the job template.
    type: bool

  verbosity:
    description:
      - Control the output level Ansible produces as the playbook runs.
    type: int
    choices: [0, 1, 2, 3, 4, 5]

  enabled:
    description:
      - Enables processing of this schedule.
    type: bool

  state:
    description:
      - Desired state of the schedule.
      - C(present) ensures the schedule exists (create or update); idempotent.
      - C(absent) removes the schedule; idempotent if already absent.
      - C(exists) reads and returns the current schedule (no change).
    type: str
    choices: ['present', 'absent', 'exists', 'enforced']
    default: 'present'

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth

notes:
  - The legacy C(organization) option (used only to disambiguate the C(unified_job_template)
    name lookup when names collide across organizations) is not carried over — name lookups
    resolve globally. Use a unique name, or the numeric ID, if this is a concern.

seealso:
  - module: ansible.controller.schedule
  - module: awx.awx.schedule
"""

EXAMPLES = """
- name: Build a schedule for Demo Job Template
  ansible.platform.schedule:
    name: "Demo Schedule"
    unified_job_template: "Demo Job Template"
    rrule: "DTSTART:20191219T130551Z RRULE:FREQ=WEEKLY;INTERVAL=1;COUNT=1"

- name: Build the same schedule using the rrule plugin
  ansible.platform.schedule:
    name: "Demo Schedule"
    unified_job_template: "Demo Job Template"
    rrule: "{{ query('awx.awx.schedule_rrule', 'week', start_date='2019-12-19 13:05:51') | first }}"

- name: Add credentials and labels applied as prompts
  ansible.platform.schedule:
    name: "Demo Schedule"
    unified_job_template: "Demo Job Template"
    rrule: "DTSTART:20191219T130551Z RRULE:FREQ=WEEKLY;INTERVAL=1;COUNT=1"
    credentials:
      - Demo Credential
    labels:
      - Demo Label

- name: Delete a schedule
  ansible.platform.schedule:
    name: "Demo Schedule"
    unified_job_template: "Demo Job Template"
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the schedule was created, updated, or deleted.
  returned: always
  type: bool

schedule:
  description: >
    The schedule resource as it exists after the operation.
    Contains only the fields accepted as module input (argspec fields) plus C(id).
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
      description: The schedule's iCal recurrence rule.
      type: str
...
"""
