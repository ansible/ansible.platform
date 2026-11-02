#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/job_launch.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: job_launch
author: Red Hat (@RedHatOfficial)
short_description: Launch a Controller job
description:
  - Launch a job from a job template on Ansible Automation Platform Controller.
  - Every invocation creates a new job; this module is not idempotent.
  - Optionally waits for the job to complete.
version_added: "2.8.0"

options:
  name:
    description:
      - Name or ID of the job template to launch.
    required: true
    type: str
    aliases:
      - job_template

  job_type:
    description:
      - Job type to use, only used if prompt for job_type is set on the template.
    choices:
      - run
      - check
    type: str

  inventory:
    description:
      - Inventory name or ID, only used if prompt for inventory is set.
    type: str

  organization:
    description:
      - Organization name or ID the job template exists in.
      - Used to scope the job template lookup when names are not unique.
    type: str

  credentials:
    description:
      - Credential names or IDs to use for the job.
      - Only used if prompt for credentials is set on the template.
    type: list
    elements: str
    aliases:
      - credential

  extra_vars:
    description:
      - Extra variables for the job template.
      - Requires ask_extra_vars or survey_enabled on the template.
    type: dict

  limit:
    description:
      - Limit to use for the job.
    type: str

  tags:
    description:
      - Specific tags to use from the playbook.
    type: list
    elements: str

  skip_tags:
    description:
      - Specific tags to skip from the playbook.
    type: list
    elements: str

  scm_branch:
    description:
      - SCM branch to run the template on.
      - Requires branch override enabled on the project.
    type: str

  verbosity:
    description:
      - Verbosity level for this job run.
    type: int
    choices: [0, 1, 2, 3, 4, 5]

  diff_mode:
    description:
      - Show the changes made by Ansible tasks where supported.
    type: bool

  credential_passwords:
    description:
      - Passwords for credentials which are set to prompt on launch.
    type: dict

  execution_environment:
    description:
      - Execution environment name or ID, only used if prompt for EE is set.
    type: str

  forks:
    description:
      - Forks to use for the job, only used if prompt for forks is set.
    type: int

  instance_groups:
    description:
      - Instance group names or IDs, only used if prompt for instance groups is set.
    type: list
    elements: str

  labels:
    description:
      - Labels to use for the job, only used if prompt for labels is set.
    type: list
    elements: str

  job_slice_count:
    description:
      - Job slice count, only used if prompt for job slice count is set.
    type: int

  job_timeout:
    description:
      - Timeout for the job on the Controller side (seconds).
      - Only used if prompt for timeout is set on the template.
    type: int

  wait:
    description:
      - Wait for the job to complete.
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
      - Only used when wait is true.
    type: int

seealso:
  - module: ansible.controller.job_launch
  - module: awx.awx.job_launch

extends_documentation_fragment:
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Launch a job
  ansible.platform.job_launch:
    name: "My Job Template"
  register: job

- name: Launch with extra vars and wait
  ansible.platform.job_launch:
    name: "My Job Template"
    extra_vars:
      var1: "value1"
    wait: true
    timeout: 300
  register: job

- name: Launch with inventory and credentials
  ansible.platform.job_launch:
    name: "My Job Template"
    inventory: "My Inventory"
    credentials:
      - "My Credential"
    wait: true
  register: job
...
"""

RETURN = """
id:
  description: Job ID of the newly launched job.
  returned: success
  type: int
  sample: 86

status:
  description: Status of the job.
  returned: success
  type: str
  sample: pending
...
"""
