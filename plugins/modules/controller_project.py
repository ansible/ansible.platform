#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/controller_project.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: controller_project
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller projects
description:
  - Create, update, or delete projects on Ansible Automation Platform Controller.
  - Projects represent a collection of playbooks from an SCM repository or local path.
  - Association endpoints (notification_templates) and copy_from are planned for a follow-up PR.
  - Wait/update_project sync functionality is planned for a follow-up PR.
version_added: "2.8.0"

options:
  name:
    description:
      - Name of the project.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  description:
    description:
      - Description of the project.
    type: str

  scm_type:
    description:
      - Type of SCM resource.
    choices: ['manual', 'git', 'svn', 'insights', 'archive']
    type: str

  scm_url:
    description:
      - URL of SCM resource.
    type: str

  local_path:
    description:
      - The server playbook directory for manual projects.
    type: str

  scm_branch:
    description:
      - The branch to use for the SCM resource.
    type: str

  scm_refspec:
    description:
      - The refspec to use for the SCM resource.
    type: str

  credential:
    description:
      - Name or ID of the credential to use with this SCM resource.
    type: str
    aliases:
      - scm_credential

  scm_clean:
    description:
      - Remove local modifications before updating.
    type: bool

  scm_delete_on_update:
    description:
      - Remove the repository completely before updating.
    type: bool

  scm_track_submodules:
    description:
      - Track submodules latest commit on specified branch.
    type: bool

  scm_update_on_launch:
    description:
      - Perform an update to the local repository before launching a job with this project.
    type: bool

  scm_update_cache_timeout:
    description:
      - Cache timeout to cache prior project syncs for a certain number of seconds.
      - Only valid if C(scm_update_on_launch) is true, otherwise ignored.
    type: int

  allow_override:
    description:
      - Allow changing the SCM branch or revision in a job template that uses this project.
    type: bool
    aliases:
      - scm_allow_override

  timeout:
    description:
      - The amount of time (in seconds) to run before the SCM update is canceled.
      - A value of 0 means no timeout.
    type: int
    aliases:
      - job_timeout

  default_environment:
    description:
      - Default execution environment name or ID to use for jobs relating to the project.
    type: str

  organization:
    description:
      - Name or ID of the organization for the project.
    type: str

  signature_validation_credential:
    description:
      - Name or ID of the credential to use for signature validation.
      - If provided, signature validation will be enabled.
    type: str

seealso:
  - module: ansible.controller.project
  - module: awx.awx.project

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Add a Git project
  ansible.platform.controller_project:
    name: "My Project"
    description: "Playbook repository"
    organization: "Default"
    scm_type: git
    scm_url: "https://github.com/ansible/ansible-tower-samples.git"
    scm_branch: master
    state: present

- name: Add a manual project
  ansible.platform.controller_project:
    name: "Manual Project"
    organization: "Default"
    scm_type: manual
    local_path: "/var/lib/awx/projects/my_project"

- name: Rename a project
  ansible.platform.controller_project:
    name: "My Project"
    new_name: "My Renamed Project"
    organization: "Default"

- name: Delete a project
  ansible.platform.controller_project:
    name: "My Renamed Project"
    organization: "Default"
    state: absent

- name: Check whether a project exists
  ansible.platform.controller_project:
    name: "My Project"
    organization: "Default"
    state: exists
  register: project_check
...
"""

RETURN = """
changed:
  description: Whether the project was created, updated, or deleted.
  returned: always
  type: bool

controller_project:
  description: >
    The project resource as it exists after the operation.
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the project.
      type: int
    name:
      description: Name of the project.
      type: str
    description:
      description: Description of the project.
      type: str
    scm_type:
      description: Type of SCM resource.
      type: str
    scm_url:
      description: URL of SCM resource.
      type: str
    scm_branch:
      description: Branch used for the SCM resource.
      type: str
    organization:
      description: Organization the project belongs to (ID).
      type: int
...
"""
