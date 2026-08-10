#!/usr/bin/python
# coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: job_template
author: "Ansible Platform Collection Contributors"
short_description: Create, update, or destroy job templates.
description:
    - Create, update, or destroy job templates in Ansible Automation Platform.
    - This module manages job templates via the Controller API.
    - Migrated from the C(awx.awx) and C(ansible.controller) collections.
options:
    name:
      description:
        - Name to use for the job template.
      required: true
      type: str
    new_name:
      description:
        - Setting this option will change the existing name (looked up via the name field).
      type: str
    copy_from:
      description:
        - Name or id to copy the job template from.
        - This will copy an existing job template and change any parameters supplied.
        - The new job template name will be the one provided in the name parameter.
        - The organization parameter is not used in this, to facilitate copy from one organization to another.
        - Provide the id or use the lookup plugin to provide the id if multiple job templates share the same name.
      type: str
    description:
      description:
        - Description to use for the job template.
      type: str
    job_type:
      description:
        - The job type to use for the job template.
      choices: ["run", "check"]
      type: str
    inventory:
      description:
        - Name, ID, or named URL of the inventory to use for the job template.
      type: str
    organization:
      description:
        - Organization name, ID, or named URL the job template exists in.
        - Used to help lookup the object, cannot be modified using this module.
        - The Organization is inferred from the associated project.
        - If not provided, will lookup by name only, which does not work with duplicates.
      type: str
    project:
      description:
        - Name, ID, or named URL of the project to use for the job template.
      type: str
    playbook:
      description:
        - Path to the playbook to use for the job template within the project provided.
      type: str
    credentials:
      description:
        - List of credential names, IDs, or named URLs to use for the job template.
      type: list
      elements: str
    execution_environment:
      description:
        - Execution Environment name, ID, or named URL to use for the job template.
      type: str
    instance_groups:
      description:
        - List of Instance Group names, IDs, or named URLs for this job template to run on.
      type: list
      elements: str
    forks:
      description:
        - The number of parallel or simultaneous processes to use while executing the playbook.
      type: int
    limit:
      description:
        - A host pattern to further constrain the list of hosts managed or affected by the playbook.
      type: str
    verbosity:
      description:
        - Control the output level Ansible produces as the playbook runs.
        - 0 - Normal, 1 - Verbose, 2 - More Verbose, 3 - Debug, 4 - Connection Debug, 5 - WinRM Debug.
      choices: [0, 1, 2, 3, 4, 5]
      type: int
    extra_vars:
      description:
        - Specify C(extra_vars) for the template.
      type: dict
    job_tags:
      description:
        - Comma separated list of the tags to use for the job template.
      type: str
    force_handlers:
      description:
        - Enable forcing playbook handlers to run even if a task fails.
      type: bool
      aliases:
        - force_handlers_enabled
    skip_tags:
      description:
        - Comma separated list of the tags to skip for the job template.
      type: str
    start_at_task:
      description:
        - Start the playbook at the task matching this name.
      type: str
    diff_mode:
      description:
        - Enable diff mode for the job template.
      type: bool
      aliases:
        - diff_mode_enabled
    use_fact_cache:
      description:
        - Enable use of fact caching for the job template.
      type: bool
      aliases:
        - fact_caching_enabled
    host_config_key:
      description:
        - Allow provisioning callbacks using this host config key.
      type: str
    ask_scm_branch_on_launch:
      description:
        - Prompt user for SCM branch on launch.
      type: bool
    ask_diff_mode_on_launch:
      description:
        - Prompt user to enable diff mode (show changes) to files when supported by modules.
      type: bool
      aliases:
        - ask_diff_mode
    ask_variables_on_launch:
      description:
        - Prompt user for extra_vars on launch.
      type: bool
      aliases:
        - ask_extra_vars
    ask_limit_on_launch:
      description:
        - Prompt user for a limit on launch.
      type: bool
      aliases:
        - ask_limit
    ask_tags_on_launch:
      description:
        - Prompt user for job tags on launch.
      type: bool
      aliases:
        - ask_tags
    ask_skip_tags_on_launch:
      description:
        - Prompt user for job tags to skip on launch.
      type: bool
      aliases:
        - ask_skip_tags
    ask_job_type_on_launch:
      description:
        - Prompt user for job type on launch.
      type: bool
      aliases:
        - ask_job_type
    ask_verbosity_on_launch:
      description:
        - Prompt user to choose a verbosity level on launch.
      type: bool
      aliases:
        - ask_verbosity
    ask_inventory_on_launch:
      description:
        - Prompt user for inventory on launch.
      type: bool
      aliases:
        - ask_inventory
    ask_credential_on_launch:
      description:
        - Prompt user for credential on launch.
      type: bool
      aliases:
        - ask_credential
    ask_execution_environment_on_launch:
      description:
        - Prompt user for execution environment on launch.
      type: bool
      aliases:
        - ask_execution_environment
    ask_forks_on_launch:
      description:
        - Prompt user for forks on launch.
      type: bool
      aliases:
        - ask_forks
    ask_instance_groups_on_launch:
      description:
        - Prompt user for instance groups on launch.
      type: bool
      aliases:
        - ask_instance_groups
    ask_job_slice_count_on_launch:
      description:
        - Prompt user for job slice count on launch.
      type: bool
      aliases:
        - ask_job_slice_count
    ask_labels_on_launch:
      description:
        - Prompt user for labels on launch.
      type: bool
      aliases:
        - ask_labels
    ask_timeout_on_launch:
      description:
        - Prompt user for timeout on launch.
      type: bool
      aliases:
        - ask_timeout
    survey_enabled:
      description:
        - Enable a survey on the job template.
      type: bool
    survey_spec:
      description:
        - JSON/YAML dict formatted survey definition.
      type: dict
    become_enabled:
      description:
        - Activate privilege escalation.
      type: bool
    allow_simultaneous:
      description:
        - Allow simultaneous runs of the job template.
      type: bool
      aliases:
        - concurrent_jobs_enabled
    timeout:
      description:
        - Maximum time in seconds to wait for a job to finish (server-side).
      type: int
    job_slice_count:
      description:
        - The number of jobs to slice into at runtime.
        - Will cause the Job Template to launch a workflow if value is greater than 1.
      type: int
    webhook_service:
      description:
        - Service that webhook requests will be accepted from.
      type: str
      choices:
        - ''
        - 'github'
        - 'gitlab'
        - 'bitbucket_dc'
    webhook_credential:
      description:
        - Personal Access Token for posting back the status to the service API.
      type: str
    scm_branch:
      description:
        - Branch to use in job run. Project default used if blank.
        - Only allowed if project allow_override field is set to true.
      type: str
    labels:
      description:
        - The labels applied to this job template.
        - Must be created with the labels module first. This will error if the label has not been created.
      type: list
      elements: str
    notification_templates_started:
      description:
        - List of notification templates to send on start.
      type: list
      elements: str
    notification_templates_success:
      description:
        - List of notification templates to send on success.
      type: list
      elements: str
    notification_templates_error:
      description:
        - List of notification templates to send on error.
      type: list
      elements: str
    prevent_instance_group_fallback:
      description:
        - Prevent falling back to instance groups set on the associated inventory or organization.
      type: bool
    opa_query_path:
      description:
        - The query path for the OPA policy to evaluate prior to job execution.
        - The query path should be formatted as package/rule.
      type: str

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth

seealso:
  - module: ansible.controller.job_template
  - module: awx.awx.job_template

notes:
  - This module is the ansible.platform equivalent of the C(awx.awx.job_template)
    and C(ansible.controller.job_template) modules.
  - JSON for survey_spec can be found in the API Documentation.
"""


EXAMPLES = """
- name: Create a job template
  ansible.platform.job_template:
    name: "Ping"
    job_type: "run"
    organization: "Default"
    inventory: "Local"
    project: "Demo"
    playbook: "ping.yml"
    credentials:
      - "Local"
      - "2nd credential"
    state: "present"
    survey_enabled: true
    survey_spec: "{{ lookup('file', 'my_survey.json') }}"

- name: Add start notification to Job Template
  ansible.platform.job_template:
    name: "Ping"
    notification_templates_started:
      - Notification1
      - Notification2

- name: Copy a job template
  ansible.platform.job_template:
    name: "copy job template"
    copy_from: "test job template"
    job_type: "run"
    inventory: "Copy Foo Inventory"
    project: "test"
    playbook: "hello_world.yml"
    state: "present"

- name: Delete a job template
  ansible.platform.job_template:
    name: "Ping"
    state: "absent"

- name: Check if a job template exists
  ansible.platform.job_template:
    name: "Ping"
    state: "exists"
"""

RETURN = """
job_template:
  description: The job_template resource data.
  returned: always
  type: dict
"""
