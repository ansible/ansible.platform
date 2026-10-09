#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: job_list
author: "Wayne Witzel III (@wwitzel3)"
short_description: List controller jobs on Ansible Automation Platform.
description:
    - List jobs from the controller API on Ansible Automation Platform.
    - Returns paginated job data with optional status filtering.
options:
    status:
      description:
        - Only list jobs with this status.
      choices: ['pending', 'waiting', 'running', 'error', 'failed', 'canceled', 'successful']
      type: str
    page:
      description:
        - Page number of the results to fetch.
      type: int
    all_pages:
      description:
        - Fetch all the pages and return a single result.
      type: bool
      default: false
    query:
      description:
        - Query used to further filter the list of jobs.
        - C({"foo":"bar"}) will be passed at C(?foo=bar).
      type: dict
mutually_exclusive:
    - ['page', 'all_pages']
extends_documentation_fragment: ansible.platform.auth
"""

EXAMPLES = """
- name: List running jobs for the testing.yml playbook
  ansible.platform.job_list:
    status: running
    query: {"playbook": "testing.yml"}
  register: testing_jobs

- name: List all failed jobs
  ansible.platform.job_list:
    status: failed
    all_pages: true
  register: failed_jobs

- name: List second page of jobs
  ansible.platform.job_list:
    page: 2
  register: jobs_page_2
"""

RETURN = """
count:
    description: Total count of objects returned.
    returned: success
    type: int
    sample: 51
next:
    description: Next page available for the listing.
    returned: success
    type: int
    sample: 3
previous:
    description: Previous page available for the listing.
    returned: success
    type: int
    sample: 1
results:
    description: A list of job objects represented as dictionaries.
    returned: success
    type: list
    sample: [{"allow_simultaneous": false, "artifacts": {}, "ask_credential_on_launch": false,
              "ask_inventory_on_launch": false, "ask_job_type_on_launch": false, "failed": false,
              "finished": "2017-02-22T15:09:05.633942Z", "force_handlers": false, "forks": 0, "id": 2,
              "inventory": 1, "job_explanation": "", "job_tags": "", "job_template": 5, "job_type": "run"}]
"""
