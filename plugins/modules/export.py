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
  - Resource selectors accept names and numeric IDs. Named URLs are resolved through the SDK when supported by the owning service.
  - Organizations, users, and teams are exported from Gateway; other resource types are exported from Controller.
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
      - Organization names or IDs to export.
      - Use C(all) to export all organizations.
    type: list
    elements: str
  controller_organizations:
    description:
      - Controller organization overlays to export. These include max_hosts,
        default_environment, Galaxy credentials, and instance-group associations.
      - Use C(all) to export all Controller organizations.
    type: list
    elements: str
  users:
    description:
      - Usernames or user IDs to export.
      - Use C(all) to export all users.
    type: list
    elements: str
  teams:
    description:
      - Team names or IDs to export.
      - Use C(all) to export all teams.
    type: list
    elements: str
  role_definitions:
    description:
      - Gateway role definition names to export.
      - Use C(all) to export all role definitions.
    type: list
    elements: str
  authenticators:
    description:
      - Gateway authenticator names to export.
      - Use C(all) to export all authenticators.
    type: list
    elements: str
  authenticator_maps:
    description:
      - Gateway authenticator-map names to export.
      - Use C(all) to export all authenticator maps.
    type: list
    elements: str
  tokens:
    description:
      - Gateway token IDs to export as masked metadata. Token values cannot be restored.
      - Use C(all) to export token metadata.
    type: list
    elements: str
  credential_types:
    description:
      - Credential type names or IDs to export.
      - Use C(all) to export all credential types.
    type: list
    elements: str
  credentials:
    description:
      - Credential names or IDs to export.
      - Use C(all) to export all credentials.
    type: list
    elements: str
  instance_groups:
    description:
      - Controller instance-group names to export, including instance associations.
      - Use C(all) to export all instance groups.
    type: list
    elements: str
  role_user_assignments:
    description:
      - Gateway role-user assignment IDs to export.
      - Use C(all) to export all role-user assignments.
    type: list
    elements: str
  role_team_assignments:
    description:
      - Gateway role-team assignment IDs to export.
      - Use C(all) to export all role-team assignments.
    type: list
    elements: str
  execution_environments:
    description:
      - Execution environment names or IDs to export.
      - Use C(all) to export all execution environments.
    type: list
    elements: str
  notification_templates:
    description:
      - Notification template names or IDs to export.
      - Use C(all) to export all notification templates.
    type: list
    elements: str
  projects:
    description:
      - Project names or IDs to export.
      - Use C(all) to export all projects.
    type: list
    elements: str
  inventory:
    description:
      - Inventory names or IDs to export.
      - Hosts and groups are included inline under each inventory.
      - Use C(all) to export all inventories.
    type: list
    elements: str
  inventory_sources:
    description:
      - Inventory source names or IDs to export.
      - Use C(all) to export all inventory sources.
    type: list
    elements: str
  job_templates:
    description:
      - Job template names or IDs to export.
      - Associations (credentials, labels, survey_spec) are included inline.
      - Use C(all) to export all job templates.
    type: list
    elements: str
  workflow_job_templates:
    description:
      - Workflow job template names or IDs to export.
      - Associations (labels, survey_spec) are included inline.
      - Use C(all) to export all workflow job templates.
    type: list
    elements: str
  labels:
    description:
      - Label names or IDs to export.
      - Use C(all) to export all labels.
    type: list
    elements: str
  schedules:
    description:
      - Schedule names or IDs to export.
      - Use C(all) to export all schedules.
    type: list
    elements: str
  max_objects:
    description:
      - Maximum number of objects to retrieve from any endpoint.
      - The module fails rather than silently truncating results when this cap is exceeded.
    type: int
    default: 10000

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
      - The restorable assets in native ansible.platform format.
      - Top-level keys are resource type names; values are lists of resource dicts.
      - Can be passed directly to the C(ansible.platform.import) module.
      - Credential input values are API-masked (for example, C($encrypted$));
        cleartext secrets are never returned and must be supplied separately when importing.
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
non_restorable:
    description:
      - Resources excluded from assets because their secrets or token values are API-masked/write-only.
      - Supply replacement secret values before importing these resources.
    returned: when masked or write-only resources are present
    type: dict

changed:
    description: Always false. Export is read-only.
    returned: success
    type: bool
    sample: false
...
"""
