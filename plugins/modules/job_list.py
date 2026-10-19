#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# Copyright: (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/job_list.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: job_list
author: Red Hat (@RedHatOfficial)
short_description: List jobs from Automation Controller.
description:
  - List jobs from the Automation Controller API with optional filters.
  - Returns a paginated list of jobs, or all jobs when C(all_pages) is set.
  - This is a read-only module; it never makes changes.
version_added: "1.0.0"

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
      - Cannot be combined with C(page).
    type: bool
    default: false

  query:
    description:
      - Additional query parameters used to filter the list of jobs.
      - "C({\\\"foo\\\":\\\"bar\\\"}) will be passed as C(?foo=bar)."
    type: dict

seealso:
  - module: ansible.controller.job_list
  - module: awx.awx.job_list

extends_documentation_fragment:
  - ansible.platform.auth
...
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

- name: List a specific page of jobs
  ansible.platform.job_list:
    page: 3
  register: page_three
...
"""

RETURN = """
count:
    description: Total count of objects returned.
    returned: success
    type: int
    sample: 51
next:
    description: URL to the next page of results, or null if on the last page.
    returned: success
    type: str
    sample: "/api/controller/v2/jobs/?page=3"
previous:
    description: URL to the previous page of results, or null if on the first page.
    returned: success
    type: str
    sample: "/api/controller/v2/jobs/?page=1"
results:
    description: A list of job objects represented as dictionaries.
    returned: success
    type: list
    sample: [{"id": 2, "job_type": "run", "status": "successful"}]
"""
