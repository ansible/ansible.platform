#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: job_cancel
author: "Wayne Witzel III (@wwitzel3)"
short_description: Cancel a controller job.
description:
    - Cancel a running job on the Automation Platform Controller.
    - If the job is not running, the module can either silently succeed
      or fail depending on the I(fail_if_not_running) parameter.
options:
    job_id:
      description:
        - ID of the job to cancel.
      required: True
      type: int
    fail_if_not_running:
      description:
        - If C(true), the module will fail when the job is not in a
          cancellable state (e.g. already completed or already canceled).
      default: False
      type: bool
extends_documentation_fragment: ansible.platform.auth
"""

EXAMPLES = """
- name: Launch a job and cancel it
  block:
    - name: Launch a Job Template
      ansible.platform.job_launch:
        job_template: "Demo Job Template"
      register: job

    - name: Cancel the running job
      ansible.platform.job_cancel:
        job_id: "{{ job.id }}"

- name: Cancel a job and fail if not running
  ansible.platform.job_cancel:
    job_id: 42
    fail_if_not_running: true

- name: Cancel a job silently (no error if already finished)
  ansible.platform.job_cancel:
    job_id: 42
"""

RETURN = """
id:
    description: ID of the job that was requested to be canceled.
    returned: success
    type: int
    sample: 94
"""
