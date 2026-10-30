#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/eda_project.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: eda_project
author: Red Hat (@RedHatOfficial)
short_description: Manage projects in EDA controller
description:
  - Create, update, or delete projects in EDA controller.
  - Projects are Git repositories that contain rulebooks and other content
    for Event-Driven Ansible.
  - This module uses the persistent connection manager for improved performance.
version_added: "2.6.0"

options:
  name:
    description:
      - The name of the project.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (rename).
    type: str

  description:
    description:
      - The description of the project.
    type: str

  url:
    description:
      - The Git URL of the project.
      - Required when creating a new project.
    type: str

  proxy:
    description:
      - Proxy server URL used to access HTTP or HTTPS servers.
    type: str

  credential:
    description:
      - The name of the EDA credential to associate with the project.
    type: str

  organization_name:
    description:
      - The name of the organization.
    type: str
    aliases:
      - organization

  scm_branch:
    description:
      - The SCM branch of the Git project.
    type: str

  state:
    description:
      - Desired state of the resource.
    type: str
    choices: ["present", "absent"]
    default: "present"

  sync:
    description:
      - Triggers the synchronization of the project.
      - This only takes effect when the project already exists.
    type: bool
    default: false

  wait:
    description:
      - Wait for the project import or sync to complete before returning.
      - When enabled, the module will poll the project status until C(import_state) is
        C(completed) or C(failed).
      - This prevents race conditions when immediately deleting or using a project
        after creation.
    type: bool
    default: true

  update_revision_on_launch:
    description:
      - Enable automatic project sync on activation launch.
    type: bool
    default: false

  scm_update_cache_timeout:
    description:
      - Cache timeout in seconds for project updates (0 = no cache, max 86400).
      - Requires O(update_revision_on_launch) to be C(true).
    type: int
    default: 0

seealso:
  - module: ansible.eda.project

extends_documentation_fragment:
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Create an EDA project
  ansible.platform.eda_project:
    name: "Example Project"
    description: "Example project description"
    url: "https://example.com/project1"
    organization_name: Default
    state: present

- name: Update the name of the project
  ansible.platform.eda_project:
    name: "Example Project"
    new_name: "Latest Example Project"
    description: "Example project description"
    url: "https://example.com/project1"
    scm_branch: "devel"
    organization_name: Default
    state: present
    update_revision_on_launch: true
    scm_update_cache_timeout: 3600

- name: Delete the project
  ansible.platform.eda_project:
    name: "Example Project"
    state: absent

- name: Create project and wait for import to complete
  ansible.platform.eda_project:
    name: "Example Project"
    url: "https://example.com/project1"
    organization_name: Default
    wait: true
    state: present

- name: Create project without waiting
  ansible.platform.eda_project:
    name: "Example Project"
    url: "https://example.com/project1"
    organization_name: Default
    wait: false
    state: present

- name: Sync an existing project
  ansible.platform.eda_project:
    name: "Example Project"
    sync: true
    state: present

- name: Create project with credential and proxy
  ansible.platform.eda_project:
    name: "Private Project"
    url: "https://private.example.com/project1"
    credential: "my-git-credential"
    proxy: "https://proxy.example.com"
    organization_name: Default
    state: present
...
"""

RETURN = """
changed:
  description: Whether the project was created, updated, or deleted.
  returned: always
  type: bool

eda_project:
  description: The project resource as it exists after the operation.
  returned: when state is present and successful
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
    url:
      description: Git URL of the project.
      type: str
...
"""
