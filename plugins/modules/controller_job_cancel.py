#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# Copyright: (c) 2025, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/controller_job_cancel.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: controller_job_cancel
author: Red Hat (@RedHatOfficial)
short_description: Cancel an Automation Controller job.
description:
  - Cancel an Automation Platform Controller job.
  - If the job has already finished, the module returns successfully with no changes.
  - This module uses the persistent connection manager for improved performance.
version_added: "1.0.0"

options:
  job_id:
    description:
      - ID of the job to cancel.
    required: true
    type: int

  fail_if_not_running:
    description:
      - Fail loudly if the job cannot be canceled (already finished).
    default: false
    type: bool

extends_documentation_fragment:
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Cancel a running job
  ansible.platform.controller_job_cancel:
    job_id: 123

- name: Cancel a job and fail if it is not running
  ansible.platform.controller_job_cancel:
    job_id: 456
    fail_if_not_running: true
"""

RETURN = """
id:
  description: The ID of the job that was requested to be canceled.
  returned: success
  type: int
  sample: 123

changed:
  description: Whether the job was actually canceled (false if already finished).
  returned: always
  type: bool

status:
  description: A short status message describing the cancel outcome.
  returned: success
  type: str
  sample: "canceled"
"""
