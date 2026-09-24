#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2020, John Westcott IV <john.westcott.iv@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/workflow_job_template.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: workflow_job_template
author: Red Hat (@RedHatOfficial)
short_description: Create, update, or destroy Automation Platform Controller workflow job templates
description:
  - Create, update, or destroy Automation Platform Controller workflow job templates.
  - Use the (not yet migrated) workflow_job_template_node module to build the workflow's node graph.
version_added: "3.0.0"

options:
  name:
    description:
      - Name of this workflow job template.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name.
    type: str

  copy_from:
    description:
      - Name or ID to copy the workflow job template from.
      - This will copy an existing workflow job template and change any parameters supplied.
      - The new workflow job template name will be the one provided in the C(name) parameter.
      - The organization parameter is not used in this, to facilitate copy from one organization to another.
    type: str

  description:
    description:
      - Optional description of this workflow job template.
    type: str

  extra_vars:
    description:
      - Variables which will be made available to jobs ran inside the workflow.
    type: dict

  job_tags:
    description:
      - Comma separated list of the tags to use for the job template.
    type: str

  ask_tags_on_launch:
    description:
      - Prompt user for job tags on launch.
    type: bool
    aliases:
      - ask_tags

  organization:
    description:
      - Organization name, ID, or named URL the workflow job template exists in.
      - Used to help lookup the object, cannot be modified using this module.
      - If not provided, will lookup by name only, which does not work with duplicates.
    type: str

  allow_simultaneous:
    description:
      - Allow simultaneous runs of the workflow job template.
    type: bool

  ask_variables_on_launch:
    description:
      - Prompt user for C(extra_vars) on launch.
    type: bool

  inventory:
    description:
      - Name, ID, or named URL of inventory applied as a prompt, assuming the workflow job template prompts for inventory.
    type: str

  limit:
    description:
      - Limit applied as a prompt, assuming the workflow job template prompts for limit.
    type: str

  scm_branch:
    description:
      - SCM branch applied as a prompt, assuming the workflow job template prompts for SCM branch.
    type: str

  ask_inventory_on_launch:
    description:
      - Prompt user for inventory on launch of this workflow job template.
    type: bool

  ask_scm_branch_on_launch:
    description:
      - Prompt user for SCM branch on launch of this workflow job template.
    type: bool

  ask_limit_on_launch:
    description:
      - Prompt user for limit on launch of this workflow job template.
    type: bool

  ask_labels_on_launch:
    description:
      - Prompt user for labels on launch.
    type: bool
    aliases:
      - ask_labels

  ask_skip_tags_on_launch:
    description:
      - Prompt user for job tags to skip on launch.
    type: bool
    aliases:
      - ask_skip_tags

  skip_tags:
    description:
      - Comma separated list of the tags to skip for the job template.
    type: str

  webhook_service:
    description:
      - Service that webhook requests will be accepted from.
    type: str
    choices:
      - github
      - gitlab
      - bitbucket_dc

  webhook_credential:
    description:
      - Name, ID, or named URL of the personal access token credential for posting back the status to the service API.
    type: str

  survey_enabled:
    description:
      - Setting that variable will prompt the user for job type on the workflow launch.
    type: bool

  survey_spec:
    description:
      - The definition of the survey associated to the workflow.
      - Providing C({}) deletes the existing survey.
    type: dict
    aliases:
      - survey

  labels:
    description:
      - The labels applied to this workflow job template.
      - Must be created with the labels module first; this will error if the label has not been created.
    type: list
    elements: str

  notification_templates_started:
    description:
      - List of notification template names, IDs, or named URLs to notify on start.
    type: list
    elements: str

  notification_templates_success:
    description:
      - List of notification template names, IDs, or named URLs to notify on success.
    type: list
    elements: str

  notification_templates_error:
    description:
      - List of notification template names, IDs, or named URLs to notify on error.
    type: list
    elements: str

  notification_templates_approvals:
    description:
      - List of notification template names, IDs, or named URLs to notify on approval.
    type: list
    elements: str

  state:
    description:
      - Desired state of the workflow job template.
      - C(present) ensures the workflow job template exists (create or update); idempotent.
      - C(absent) removes the workflow job template; idempotent if already absent.
      - C(exists) reads and returns the current workflow job template (no change).
    type: str
    choices: ['present', 'absent', 'exists', 'enforced']
    default: 'present'

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth

notes:
  - The legacy C(workflow_nodes) (alias C(schema)) and C(destroy_current_nodes)
    options for building the workflow's node graph are not carried over — node
    graph management is a separate resource (workflow_job_template_node, not
    yet migrated) with its own CRUD and association surface, not a field of
    the workflow_job_template itself.

seealso:
  - module: ansible.controller.workflow_job_template
  - module: awx.awx.workflow_job_template
"""

EXAMPLES = """
- name: Create a workflow job template
  ansible.platform.workflow_job_template:
    name: example-workflow
    description: created by Ansible Playbook
    organization: Default

- name: Create a workflow job template with a survey and notifications
  ansible.platform.workflow_job_template:
    name: example-workflow
    inventory: Demo Inventory
    extra_vars:
      foo: bar
    survey_enabled: true
    survey_spec:
      name: ""
      description: ""
      spec:
        - question_name: "Environment"
          variable: environment
          type: text
          required: true
    notification_templates_success:
      - Slack Notification

- name: Copy a workflow job template
  ansible.platform.workflow_job_template:
    name: copy-workflow
    copy_from: example-workflow
    organization: Foo

- name: Delete a workflow job template
  ansible.platform.workflow_job_template:
    name: example-workflow
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the workflow job template was created, updated, or deleted.
  returned: always
  type: bool

workflow_job_template:
  description: >
    The workflow job template resource as it exists after the operation.
    Contains only the fields accepted as module input (argspec fields) plus C(id).
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the workflow job template.
      type: int
    name:
      description: Name of the workflow job template.
      type: str
    organization:
      description: ID of the organization the workflow job template belongs to.
      type: int
...
"""
