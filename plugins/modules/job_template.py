#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: job_template
author: Red Hat (@RedHatOfficial)
short_description: Manage a controller job template.
description:
    - Create, update, or delete an automation platform controller job template.
    - Association fields (C(credentials), C(labels), notification templates, C(instance_groups)), C(copy_from), and
      C(survey_spec) are not yet supported by this module and will be added in a follow-up release.
options:
    name:
      required: true
      type: str
      description: Name to use for the job template.
    new_name:
      type: str
      description: Setting this option will change the existing name (looked up via the name field).
    description:
      type: str
      description: Description to use for the job template.
    job_type:
      type: str
      choices: ["run", "check"]
      description: The job type to use for the job template.
    inventory:
      type: str
      description: Name or ID of the inventory to use for the job template.
    organization:
      type: str
      description:
        - Name or ID of the organization used to disambiguate C(project) when multiple projects share the same name.
        - The organization is not itself a field of the job template; it is inferred from the associated project.
    project:
      type: str
      description: Name or ID of the project to use for the job template.
    playbook:
      type: str
      description: Path to the playbook to use for the job template within the project provided.
    scm_branch:
      type: str
      description: Branch to use in job run. Project default used if blank. Only allowed if project allow_override field is set to true.
    forks:
      type: int
      description: The number of parallel or simultaneous processes to use while executing the playbook.
    limit:
      type: str
      description: A host pattern to further constrain the list of hosts managed or affected by the playbook.
    verbosity:
      type: int
      choices: [0, 1, 2, 3, 4, 5]
      description: Control the output level Ansible produces as the playbook runs. 0 - Normal, 1 - Verbose, 2 - More Verbose, 3 - Debug, 4 - Connection
        Debug, 5 - WinRM Debug.
    extra_vars:
      type: dict
      description: Specify C(extra_vars) for the template.
    job_tags:
      type: str
      description: Comma separated list of the tags to use for the job template.
    force_handlers:
      type: bool
      description: Enable forcing playbook handlers to run even if a task fails.
    skip_tags:
      type: str
      description: Comma separated list of the tags to skip for the job template.
    start_at_task:
      type: str
      description: Start the playbook at the task matching this name.
    timeout:
      type: int
      description: Maximum time in seconds to wait for a job to finish (server-side).
    use_fact_cache:
      type: bool
      description: Enable use of fact caching for the job template.
    execution_environment:
      type: str
      description: Name or ID of the execution environment to use for the job template.
    host_config_key:
      type: str
      description: Allow provisioning callbacks using this host config key.
    ask_scm_branch_on_launch:
      type: bool
      description: Prompt user for (scm branch) on launch.
    ask_diff_mode_on_launch:
      type: bool
      description: Prompt user to enable diff mode (show changes) to files when supported by modules.
    ask_variables_on_launch:
      type: bool
      description: Prompt user for (extra_vars) on launch.
    ask_limit_on_launch:
      type: bool
      description: Prompt user for a limit on launch.
    ask_tags_on_launch:
      type: bool
      description: Prompt user for job tags on launch.
    ask_skip_tags_on_launch:
      type: bool
      description: Prompt user for job tags to skip on launch.
    ask_job_type_on_launch:
      type: bool
      description: Prompt user for job type on launch.
    ask_verbosity_on_launch:
      type: bool
      description: Prompt user to choose a verbosity level on launch.
    ask_inventory_on_launch:
      type: bool
      description: Prompt user for inventory on launch.
    ask_credential_on_launch:
      type: bool
      description: Prompt user for credential on launch.
    ask_execution_environment_on_launch:
      type: bool
      description: Prompt user for execution environment on launch.
    ask_labels_on_launch:
      type: bool
      description: Prompt user for labels on launch.
    ask_forks_on_launch:
      type: bool
      description: Prompt user for forks on launch.
    ask_job_slice_count_on_launch:
      type: bool
      description: Prompt user for job slice count on launch.
    ask_timeout_on_launch:
      type: bool
      description: Prompt user for timeout on launch.
    ask_instance_groups_on_launch:
      type: bool
      description: Prompt user for instance groups on launch.
    survey_enabled:
      type: bool
      description: Enable a survey on the job template.
    become_enabled:
      type: bool
      description: Activate privilege escalation.
    diff_mode:
      type: bool
      description: Enable diff mode for the job template.
    allow_simultaneous:
      type: bool
      description: Allow simultaneous runs of the job template.
    job_slice_count:
      type: int
      description: The number of jobs to slice into at runtime. Will cause the Job Template to launch a workflow if value is greater than 1.
    webhook_service:
      type: str
      choices: ["", "github", "gitlab", "bitbucket_dc"]
      description: Service that webhook requests will be accepted from.
    webhook_credential:
      type: str
      description: Name or ID of the personal access token credential for posting back the status to the service API.
    prevent_instance_group_fallback:
      type: bool
      description:
        - Prevent falling back to instance groups set on the associated inventory or organization.
        - If enabled and an empty list of instance groups is provided, the global instance groups will be applied.
    opa_query_path:
      type: str
      description: The query path for the OPA policy to evaluate prior to job execution. The query path should be formatted as package/rule.

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth

seealso:
  - module: ansible.controller.job_template
  - module: awx.awx.job_template
"""

EXAMPLES = """
- name: Create a job template
  ansible.platform.job_template:
    name: Ping
    job_type: run
    organization: Default
    inventory: Local
    project: Demo
    playbook: ping.yml
    state: present

- name: Rename a job template
  ansible.platform.job_template:
    name: Ping
    new_name: Ping check
    state: present

- name: Delete a job template
  ansible.platform.job_template:
    name: Ping check
    state: absent

- name: Check whether a job template exists
  ansible.platform.job_template:
    name: Ping
    state: exists
...
"""

RETURN = """
job_template:
  description: The job template resource data.
  returned: always
  type: dict
...
"""
