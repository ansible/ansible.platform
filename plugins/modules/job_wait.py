#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/job_wait.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: job_wait
author: Red Hat (@RedHatOfficial)
short_description: Wait for an Automation Platform Controller job to finish
description:
  - Wait for an Automation Platform Controller job, project update, inventory
    update, or workflow job to finish and report its final status.
  - This module never launches anything; it only waits on an already-running
    or already-finished job.
version_added: "3.0.0"

options:
  job_id:
    description:
      - ID of the job to monitor.
    required: true
    type: int

  job_type:
    description:
      - Type of job to wait for.
    choices: ['jobs', 'project_updates', 'inventory_updates', 'workflow_jobs']
    default: 'jobs'
    type: str

  interval:
    description:
      - The interval in seconds to request an update from the controller.
    default: 2
    type: float

  timeout:
    description:
      - Maximum time in seconds to wait for the job to finish.
      - When this option is omitted, polling is capped at 3600 seconds (1 hour).
        Set explicitly to use a different limit.
    type: int

extends_documentation_fragment:
  - ansible.platform.auth

seealso:
  - module: ansible.controller.job_wait
  - module: awx.awx.job_wait

notes:
  - The legacy default C(interval) behaviour (averaging undocumented min/max
    bounds when unset) is not carried over — C(interval) always defaults to 2
    seconds, matching the module's documented default.
"""

EXAMPLES = """
- name: Launch a job
  ansible.platform.job_launch:
    name: "My Job Template"
  register: job

- name: Wait for the job, max 120s
  ansible.platform.job_wait:
    job_id: "{{ job.id }}"
    timeout: 120
...
"""

RETURN = """
id:
  description: Job id that was waited on.
  returned: success
  type: int
  sample: 99

status:
  description:
    - Final status of the job.
    - The task fails (C(failed=true)) if this is C(error), C(failed), or C(canceled).
  returned: success
  type: str
  sample: successful

started:
  description: Timestamp of when the job started running.
  returned: success
  type: str
  sample: "2026-03-01T17:03:53Z"

finished:
  description: Timestamp of when the job finished running.
  returned: success
  type: str
  sample: "2026-03-01T17:04:04Z"

elapsed:
  description: Total time in seconds the job took to run.
  returned: success
  type: float
  sample: 10.879
...
"""
