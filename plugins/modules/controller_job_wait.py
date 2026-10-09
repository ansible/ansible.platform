#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# Copyright: (c) 2025, Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/controller_job_wait.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: controller_job_wait
author: Red Hat (@RedHatOfficial)
short_description: Wait for an Automation Controller job to finish.
description:
  - Wait for an Automation Controller job to finish and report success or failure.
  - This module polls an existing job by ID and never creates or modifies resources.
version_added: "3.0.0"

options:
  job_id:
    description:
      - ID of the job to monitor.
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
      - Maximum time in seconds to wait for a job to finish.
    type: int
  job_type:
    description:
      - Type of job to wait for, determines the API endpoint used for polling.
    choices: ['project_updates', 'jobs', 'inventory_updates', 'workflow_jobs']
    default: 'jobs'
    type: str

seealso:
  - module: ansible.controller.job_wait
  - module: awx.awx.job_wait

extends_documentation_fragment: ansible.platform.auth
"""

EXAMPLES = """
- name: Launch a job
  ansible.platform.controller_job_launch:
    job_template: "My Job Template"
  register: job

- name: Wait for job max 120s
  ansible.platform.controller_job_wait:
    job_id: "{{ job.id }}"
    timeout: 120

- name: Wait for a project update
  ansible.platform.controller_job_wait:
    job_id: "{{ project_update.id }}"
    job_type: project_updates
    timeout: 60
"""

RETURN = """
id:
    description: Job id that is being waited on.
    returned: success
    type: int
    sample: 99
elapsed:
    description: Total time in seconds the job took to run.
    returned: success
    type: float
    sample: 10.879
started:
    description: Timestamp of when the job started running.
    returned: success
    type: str
    sample: "2017-03-01T17:03:53.200234Z"
finished:
    description: Timestamp of when the job finished running.
    returned: success
    type: str
    sample: "2017-03-01T17:04:04.078782Z"
status:
    description: Current status of job.
    returned: success
    type: str
    sample: successful
"""
