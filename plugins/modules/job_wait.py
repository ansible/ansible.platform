#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: job_wait
author: "Wayne Witzel III (@wwitzel3)"
short_description: Wait for an Automation Platform Controller job to finish.
description:
    - Wait for an Automation Platform Controller job to finish and report success or failure.
    - See U(https://www.ansible.com/tower) for an overview.
options:
    job_id:
      description:
        - ID of the job to monitor.
      required: True
      type: int
    interval:
      description:
        - The interval in seconds to request an update from the controller.
      required: False
      default: 2
      type: float
    timeout:
      description:
        - Maximum time in seconds to wait for a job to finish.
      type: int
    job_type:
      description:
        - Job type to wait for.
      choices: ['project_updates', 'jobs', 'inventory_updates', 'workflow_jobs']
      default: 'jobs'
      type: str

extends_documentation_fragment: ansible.platform.auth
"""

EXAMPLES = """
- name: Launch a job
  ansible.platform.job_launch:
    job_template: "My Job Template"
  register: job

- name: Wait for job max 120s
  ansible.platform.job_wait:
    job_id: "{{ job.id }}"
    timeout: 120

- name: Wait for a workflow job
  ansible.platform.job_wait:
    job_id: "{{ workflow.id }}"
    job_type: "workflow_jobs"
"""

RETURN = """
id:
    description: Job ID that is being waited on.
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
    description: Current status of the job.
    returned: success
    type: str
    sample: successful
"""
