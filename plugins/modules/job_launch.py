#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/job_launch.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: job_launch
author: Red Hat (@RedHatOfficial)
short_description: Launch an Ansible job
description:
  - Launch an Ansible Automation Platform Controller job.
  - This module always creates a new job execution; it is not idempotent.
version_added: "3.0.0"

options:
  name:
    description:
      - Name of the job template to use.
    required: true
    type: str
    aliases:
      - job_template

  job_type:
    description:
      - Job type to use for the job, only used if prompt for job_type is set.
    choices: ['run', 'check']
    type: str

  inventory:
    description:
      - Inventory name, ID, or named URL to use for the job, only used if prompt for inventory is set.
    type: str

  credentials:
    description:
      - Credential names, IDs, or named URLs to use for the job, only used if prompt for credential is set.
    type: list
    elements: str
    aliases:
      - credential

  extra_vars:
    description:
      - extra_vars to use for the job template.
      - C(ask_extra_vars) needs to be set to C(true) on the job template for this to take effect.
    type: dict

  limit:
    description:
      - Limit to use for the job template.
    type: str

  tags:
    description:
      - Specific tags to use from the playbook.
    type: list
    elements: str

  scm_branch:
    description:
      - A specific branch of the SCM project to run the template on.
      - This is only applicable if the project allows for branch override.
    type: str

  skip_tags:
    description:
      - Specific tags to skip from the playbook.
    type: list
    elements: str

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
      - Execution environment name, ID, or named URL to use for the job, only used if prompt for execution environment is set.
    type: str

  forks:
    description:
      - Forks to use for the job, only used if prompt for forks is set.
    type: int

  instance_groups:
    description:
      - Instance group names, IDs, or named URLs to use for the job, only used if prompt for instance groups is set.
    type: list
    elements: str

  job_slice_count:
    description:
      - Job slice count to use for the job, only used if prompt for job slice count is set.
    type: int

  labels:
    description:
      - Label names to use for the job, only used if prompt for labels is set.
    type: list
    elements: str

  job_timeout:
    description:
      - Timeout to use for the job, only used if prompt for timeout is set.
      - This parameter is sent through the API to the job.
    type: int

  wait:
    description:
      - Wait for the job to complete.
    default: false
    type: bool

  interval:
    description:
      - The interval in seconds to request an update from the controller.
    default: 2
    type: float

  timeout:
    description:
      - If waiting for the job to complete this will abort after this
        amount of seconds.
      - When C(wait=true) and this option is omitted, polling is capped at
        3600 seconds (1 hour). Set explicitly to use a different limit.
    type: int

extends_documentation_fragment:
  - ansible.platform.auth

notes:
  - The legacy C(organization) option (used only to disambiguate the job template
    name lookup when names collide across organizations) is not carried over —
    name lookups resolve globally via C(unified_job_templates). Use a unique name,
    or the numeric ID, if this is a concern.
  - The legacy client-side validation that rejects prompt fields the job template
    does not allow to be overridden (its C(ask_*_on_launch) flags) is not
    reproduced — Controller's own API validation on the launch call is treated as
    sufficient.

seealso:
  - module: ansible.controller.job_launch
  - module: awx.awx.job_launch
"""

EXAMPLES = """
- name: Launch a job
  ansible.platform.job_launch:
    name: "My Job Template"
  register: job

- name: Launch a job template with extra_vars, waiting for it to finish
  ansible.platform.job_launch:
    name: "My Job Template"
    extra_vars:
      var1: "My First Variable"
      var2: "My Second Variable"
    wait: true

- name: Launch a job with inventory and credentials
  ansible.platform.job_launch:
    name: "My Job Template"
    inventory: "My Inventory"
    credentials:
      - "My Credential"
      - "Supplementary Credential"
...
"""

RETURN = """
id:
  description: ID of the newly launched job.
  returned: success
  type: int
  sample: 86
status:
  description:
    - Status of the launched job.
    - With C(wait=false) this is always C(pending) — the job has only just
      been launched. With C(wait=true) this is the terminal status reported by
      Controller once the job finishes; the task fails (C(failed=true)) if
      that terminal status is C(error), C(failed), or C(canceled).
  returned: success
  type: str
  sample: pending
...
"""
