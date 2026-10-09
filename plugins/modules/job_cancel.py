#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# Copyright: (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/job_cancel.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: job_cancel
author: Red Hat (@RedHatOfficial)
short_description: Cancel an Automation Platform Controller job
description:
  - Cancel an Automation Platform Controller job.
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
      - Fail loudly if the job cannot be canceled.
    default: false
    type: bool

extends_documentation_fragment:
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Cancel a running job
  ansible.platform.job_cancel:
    job_id: "{{ job.id }}"

- name: Cancel a job, fail if not running
  ansible.platform.job_cancel:
    job_id: 42
    fail_if_not_running: true
"""

RETURN = """
id:
  description: Job ID that was requested to cancel.
  returned: success
  type: int
  sample: 94

changed:
  description: Whether the job was canceled.
  returned: always
  type: bool
"""
