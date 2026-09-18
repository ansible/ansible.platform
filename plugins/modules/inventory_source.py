#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2018, Adrien Fleury <fleu42@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/inventory_source.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: inventory_source
author: Red Hat (@RedHatOfficial)
short_description: Create, update, or destroy Automation Platform Controller inventory sources
description:
  - Create, update, or destroy Automation Platform Controller inventory sources.
version_added: "3.0.0"

options:
  name:
    description:
      - The name to use for the inventory source.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  description:
    description:
      - The description to use for the inventory source.
    type: str

  inventory:
    description:
      - Inventory name, ID, or named URL the source should be made a member of.
    required: true
    type: str

  source:
    description:
      - The source to use for this inventory source.
      - Required when creating a new inventory source.
    choices: ["scm", "ec2", "gce", "azure_rm", "vmware", "satellite6", "openstack", "rhv", "controller", "insights", "terraform",
              "openshift_virtualization"]
    type: str

  source_path:
    description:
      - For an SCM based inventory source, the source path points to the file within the repo to use as an inventory.
    type: str

  source_vars:
    description:
      - The variables or environment fields to apply to this source type.
    type: dict

  enabled_var:
    description:
      - The variable to use to determine enabled state, e.g. C(status.power_state).
    type: str

  enabled_value:
    description:
      - Value when the host is considered enabled, e.g. C(powered_on).
    type: str

  host_filter:
    description:
      - If specified, only hosts that match this regular expression will be imported.
    type: str

  limit:
    description:
      - Enter host, group, or pattern match.
    type: str

  credential:
    description:
      - Credential name, ID, or named URL to use for the source.
    type: str

  execution_environment:
    description:
      - Execution Environment name, ID, or named URL to use for the source.
    type: str

  overwrite:
    description:
      - Delete child groups and hosts not found in source.
    type: bool

  overwrite_vars:
    description:
      - Override vars in child groups and hosts with those from the external source.
    type: bool

  timeout:
    description:
      - The amount of time (in seconds) to run before the task is canceled.
    type: int

  verbosity:
    description:
      - The verbosity level to run this inventory source under.
    type: int
    choices: [0, 1, 2]

  update_on_launch:
    description:
      - Refresh inventory data from its source each time a job is run.
    type: bool

  update_cache_timeout:
    description:
      - Time in seconds to consider an inventory sync to be current.
    type: int

  source_project:
    description:
      - Project name, ID, or named URL to use as source with the C(scm) option.
    type: str

  scm_branch:
    description:
      - Inventory source SCM branch.
      - Project must have branch override enabled.
    type: str

  notification_templates_started:
    description:
      - List of notification template names to send notifications to on start.
    type: list
    elements: str

  notification_templates_success:
    description:
      - List of notification template names to send notifications to on success.
    type: list
    elements: str

  notification_templates_error:
    description:
      - List of notification template names to send notifications to on error.
    type: list
    elements: str

  state:
    description:
      - Desired state of the inventory source.
      - C(present) ensures the inventory source exists (create or update); idempotent.
      - C(absent) removes the inventory source; idempotent if already absent.
      - C(exists) reads and returns the current inventory source (no change).
    type: str
    choices: ['present', 'absent', 'exists', 'enforced']
    default: 'present'

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth

notes:
  - The legacy C(organization) option (used only to disambiguate C(inventory)/C(source_project)
    name lookups when names collide across organizations) is not carried over — name lookups
    resolve globally. Use a unique name, or the numeric ID, if this is a concern.
  - The legacy C(custom_virtualenv) option is not carried over — Controller's API no longer
    supports per-inventory-source custom virtualenvs.

seealso:
  - module: ansible.controller.inventory_source
  - module: awx.awx.inventory_source
"""

EXAMPLES = """
- name: Add an inventory source
  ansible.platform.inventory_source:
    name: "source-inventory"
    description: Source for inventory
    inventory: previously-created-inventory
    source: scm
    credential: previously-created-credential
    source_project: previously-created-project
    overwrite: true
    update_on_launch: true
    source_vars:
      private: false

- name: Check whether an inventory source exists (no change)
  ansible.platform.inventory_source:
    name: "source-inventory"
    inventory: previously-created-inventory
    state: exists

- name: Delete an inventory source
  ansible.platform.inventory_source:
    name: "source-inventory"
    inventory: previously-created-inventory
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the inventory source was created, updated, or deleted.
  returned: always
  type: bool

inventory_source:
  description: >
    The inventory source resource as it exists after the operation.
    Contains only the fields accepted as module input (argspec fields) plus C(id).
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the inventory source.
      type: int
    name:
      description: Name of the inventory source.
      type: str
    inventory:
      description: ID of the inventory the source belongs to.
      type: int
    source:
      description: The source type.
      type: str
...
"""
