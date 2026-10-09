#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2018, Adrien Fleury <fleu42@gmail.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/inventory_source.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: inventory_source
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller inventory sources
description:
  - Create, update, or delete inventory sources on Ansible Automation Platform Controller.
  - Inventory sources define how hosts are imported from external systems.
  - Notification template associations are planned for a follow-up PR.
version_added: "2.8.0"

options:
  name:
    description:
      - The name of the inventory source.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  description:
    description:
      - The description of the inventory source.
    type: str

  inventory:
    description:
      - Inventory name or ID the source belongs to.
    required: true
    type: str

  source:
    description:
      - The source type for this inventory source.
    choices:
      - scm
      - ec2
      - gce
      - azure_rm
      - vmware
      - satellite6
      - openstack
      - rhv
      - controller
      - insights
      - terraform
      - openshift_virtualization
    type: str

  source_path:
    description:
      - For an SCM-based inventory source, the source path points to the file within the repo to use as an inventory.
    type: str

  source_vars:
    description:
      - The variables or environment fields to apply to this source type.
      - Accepts a YAML/JSON dictionary which will be serialized as a JSON string.
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
      - If specified, only import hosts that match this regular expression.
    type: str

  limit:
    description:
      - Enter host, group, or pattern match.
    type: str

  credential:
    description:
      - Credential name or ID to use for the source.
    type: str

  execution_environment:
    description:
      - Execution Environment name or ID to use for the source.
    type: str

  overwrite:
    description:
      - Delete child groups and hosts not found in source.
    type: bool

  overwrite_vars:
    description:
      - Override vars in child groups and hosts with those from external source.
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
      - Project name or ID to use as source with SCM option.
    type: str

  scm_branch:
    description:
      - Inventory source SCM branch. Project must have branch override enabled.
    type: str

seealso:
  - module: ansible.controller.inventory_source
  - module: awx.awx.inventory_source

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Add an inventory source
  ansible.platform.inventory_source:
    name: "ec2-source"
    description: "EC2 inventory source"
    inventory: "Production Inventory"
    source: ec2
    credential: "AWS Credential"
    overwrite: true
    update_on_launch: true
    state: present

- name: Add an SCM inventory source
  ansible.platform.inventory_source:
    name: "scm-source"
    inventory: "Production Inventory"
    source: scm
    source_project: "My Project"
    source_path: "inventories/hosts.yml"

- name: Delete an inventory source
  ansible.platform.inventory_source:
    name: "ec2-source"
    inventory: "Production Inventory"
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
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the inventory source.
      type: int
    name:
      description: Name of the inventory source.
      type: str
    description:
      description: Description of the inventory source.
      type: str
    inventory:
      description: Inventory the source belongs to (ID).
      type: int
    source:
      description: The source type.
      type: str
    credential:
      description: Credential used by the source (ID).
      type: int
    execution_environment:
      description: Execution environment used by the source (ID).
      type: int
    source_project:
      description: Project used as SCM source (ID).
      type: int
...
"""
