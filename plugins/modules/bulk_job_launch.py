#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: bulk_job_launch
author: "Ansible Platform Collection Contributors"
short_description: Bulk job launch in Controller.
description:
    - Launch multiple jobs in a single API request to Controller.
    - Creates a workflow where each node corresponds to an item in the C(jobs) list.
    - Top-level options are inherited by launched jobs when prompt on launch is enabled.
options:
    jobs:
        description:
            - List of jobs to launch.
        required: true
        type: list
        elements: dict
        suboptions:
            unified_job_template:
                description:
                    - Job template ID to use when launching.
                type: int
                required: true
            inventory:
                description:
                    - Inventory ID applied as a prompt, if job template prompts for inventory.
                type: int
            execution_environment:
                description:
                    - Execution environment ID applied as a prompt, if job template prompts for execution environments.
                type: int
            instance_groups:
                description:
                    - Instance group IDs applied as a prompt, if job template prompts for instance groups.
                type: list
                elements: int
            credentials:
                description:
                    - Credential IDs applied as a prompt, if job template prompts for credentials.
                type: list
                elements: int
            labels:
                description:
                    - Label IDs to use for the job, if job template prompts for labels.
                type: list
                elements: int
            extra_data:
                description:
                    - Extra variables to apply at launch time, if job template prompts for extra variables.
                type: dict
                default: {}
            diff_mode:
                description:
                    - Show the changes made by Ansible tasks where supported.
                type: bool
            verbosity:
                description:
                    - Verbosity level for this job run.
                type: int
                choices: [0, 1, 2, 3, 4, 5]
            scm_branch:
                description:
                    - SCM branch applied as a prompt, if job template prompts for SCM branch.
                type: str
            job_type:
                description:
                    - Job type applied as a prompt, if job template prompts for job type.
                type: str
                choices:
                    - run
                    - check
            job_tags:
                description:
                    - Job tags applied as a prompt, if job template prompts for job tags.
                type: str
            skip_tags:
                description:
                    - Tags to skip, applied as a prompt, if job template prompts for job tags.
                type: str
            limit:
                description:
                    - Limit to act on, applied as a prompt, if job template prompts for limit.
                type: str
            forks:
                description:
                    - Number of parallel processes to use while executing the playbook.
                type: int
            job_slice_count:
                description:
                    - Number of jobs to slice into at runtime.
                type: int
                default: 1
            identifier:
                description:
                    - Identifier for the resulting workflow node that represents this job.
                type: str
            timeout:
                description:
                    - Maximum time in seconds to wait for a job to finish (server-side).
                type: int
    name:
        description:
            - Name of the bulk job that is created.
        required: false
        type: str
    description:
        description:
            - Optional description of this bulk job.
        type: str
    organization:
        description:
            - Organization for the bulk job. Required if the user belongs to more than one.
        type: str
    inventory:
        description:
            - Inventory name or ID to use for all jobs, if prompt for inventory is enabled.
        type: str
    limit:
        description:
            - Limit to use for all jobs in the bulk launch.
        type: str
    scm_branch:
        description:
            - SCM branch to run the template on, if the project allows branch override.
        type: str
    extra_vars:
        description:
            - Extra variables to apply to all jobs. Extends extra_data at the individual job level.
        type: dict
    job_tags:
        description:
            - Comma-separated list of playbook tags specifying which parts to execute.
        type: str
    skip_tags:
        description:
            - Comma-separated list of playbook tags to skip.
        type: str
    wait:
        description:
            - Wait for the bulk job to complete.
        default: true
        type: bool
    interval:
        description:
            - Interval in seconds between polling requests.
        default: 2
        type: float
    timeout:
        description:
            - Maximum time in seconds to wait for the bulk job to finish.
        type: int
seealso:
    - module: ansible.controller.bulk_job_launch
    - module: awx.awx.bulk_job_launch
extends_documentation_fragment: ansible.platform.auth
version_added: "2.8.0"
"""

EXAMPLES = """
- name: Launch bulk jobs
  ansible.platform.bulk_job_launch:
    name: My Bulk Job Launch
    jobs:
      - unified_job_template: 7
        skip_tags: foo
      - unified_job_template: 10
        limit: foo
        extra_data:
          food: carrot
    limit: bar
    extra_vars:
      food: grape
    organization: Default
    inventory: "Demo Inventory"

- name: Launch bulk jobs without waiting
  ansible.platform.bulk_job_launch:
    name: Quick Bulk Launch
    jobs:
      - unified_job_template: 7
      - unified_job_template: 10
    wait: false
"""

RETURN = """
id:
    description: ID of the workflow job created by the bulk launch.
    returned: success
    type: int
    sample: 42
status:
    description: Status of the bulk job.
    returned: success
    type: str
    sample: successful
job_info:
    description: Full response from the bulk job launch API.
    returned: success
    type: dict
"""
