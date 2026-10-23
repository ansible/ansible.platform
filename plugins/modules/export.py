#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/export.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: export
author: Red Hat (@RedHatOfficial)
short_description: Export resources from Ansible Automation Platform.
description:
  - Export Controller and Gateway resources as a structured asset dict.
  - Output uses the native ansible.platform format where FK references are
    resolved to resource names and associations are flattened into the
    resource dict. The output can be piped directly into the
    C(ansible.platform.import) module or role.
  - This is a read-only module; it never makes changes. C(changed) is always C(false).
version_added: "2.7.0"

options:
  all:
    description:
      - Export all assets of all resource types.
      - When C(true), per-resource-type filters are ignored.
    type: bool
    default: false
  organizations:
    description:
      - Organization names to export.
      - Use C(all) to export all organizations.
    type: list
    elements: str
  users:
    description:
      - User usernames to export.
      - Use C(all) to export all users.
    type: list
    elements: str
  teams:
    description:
      - Team names to export.
      - Use C(all) to export all teams.
    type: list
    elements: str
  credential_types:
    description:
      - Credential type names to export.
      - Use C(all) to export all credential types.
    type: list
    elements: str
  credentials:
    description:
      - Credential names to export.
      - Use C(all) to export all credentials.
    type: list
    elements: str
  execution_environments:
    description:
      - Execution environment names to export.
      - Use C(all) to export all execution environments.
    type: list
    elements: str
  notification_templates:
    description:
      - Notification template names to export.
      - Use C(all) to export all notification templates.
    type: list
    elements: str
  projects:
    description:
      - Project names to export.
      - Use C(all) to export all projects.
    type: list
    elements: str
  inventory:
    description:
      - Inventory names to export.
      - Hosts and groups are included inline under each inventory.
      - Use C(all) to export all inventories.
    type: list
    elements: str
  inventory_sources:
    description:
      - Inventory source names to export.
      - Use C(all) to export all inventory sources.
    type: list
    elements: str
  job_templates:
    description:
      - Job template names to export.
      - Associations (credentials, labels, survey_spec) are included inline.
      - Use C(all) to export all job templates.
    type: list
    elements: str
  workflow_job_templates:
    description:
      - Workflow job template names to export.
      - Associations (labels, survey_spec) are included inline.
      - Use C(all) to export all workflow job templates.
    type: list
    elements: str
  schedules:
    description:
      - Schedule names to export.
      - Use C(all) to export all schedules.
    type: list
    elements: str

seealso:
  - module: awx.awx.export
  - module: ansible.controller.export
  - module: ansible.platform.import

extends_documentation_fragment:
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Export all assets
  ansible.platform.export:
    all: true
  register: export_output

- name: Export all inventories
  ansible.platform.export:
    inventory: all
  register: inventory_export

- name: Export specific job template and all credentials
  ansible.platform.export:
    job_templates: ["My Template"]
    credentials: all
  register: selective_export

- name: Export and immediately import to another instance
  ansible.platform.export:
    all: true
  register: export_output

- name: Import the exported assets
  ansible.platform.import:
    assets: "{{ export_output.assets }}"
  delegate_to: other_gateway
...
"""

RETURN = """
assets:
    description:
      - The exported assets in native ansible.platform format.
      - Top-level keys are resource type names; values are lists of resource dicts.
      - Can be passed directly to the C(ansible.platform.import) module.
    returned: success
    type: dict
    sample:
      organizations:
        - name: Default
          description: ""
      credentials:
        - name: My Cred
          credential_type: Machine
          organization: Default
changed:
    description: Always false. Export is read-only.
    returned: success
    type: bool
    sample: false
...
"""
