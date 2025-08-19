#!/usr/bin/python
# coding: utf-8

# (c) 2025, Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: role_definition
author: Rohit Thakur (@rohitthakur2590)
short_description: Configure a gateway role definition.
description:
    - Create, update, or delete role definitions on the Automation Platform Gateway.
    - A role definition consists of a name, content type, and permissions, and is platform-wide.
options:
    name:
      required: true
      type: str
      description: The name of the role definition (must be unique)
    new_name:
      type: str
      description: Setting this option will change the existing name (looked up via the name field)
    description:
      type: str
      description: Description of the role definition
    content_type:
      type: str
      required: true
      description: The content type for which the role applies (e.g., awx.inventory)
    permissions:
      type: list
      elements: str
      required: true
      description: List of permission strings to associate with the role (e.g., awx.view_inventory)
    state:
      type: str
      choices: [present, absent, exists, enforced]
      default: present
      description: Desired state of the role definition

extends_documentation_fragment:
- ansible.platform.state
- ansible.platform.auth
"""

EXAMPLES = """
- name: Create a role definition
  ansible.platform.role_definition:
    name: Organization Inventory Admin
    description: Grants full inventory access
    content_type: awx.inventory
    permissions:
      - awx.view_inventory
      - awx.change_inventory
    state: present

- name: Delete a role definition
  ansible.platform.role_definition:
    name: Organization Inventory Admin
    state: absent
"""

from ..module_utils.aap_module import AAPModule  # noqa
from ..module_utils.aap_role_definition import AAPRoleDefinition  # noqa


def main():
    argument_spec = dict(
        name=dict(type="str", required=True),
        new_name=dict(type="str"),
        description=dict(type="str"),
        content_type=dict(type="str", required=True),
        permissions=dict(type="list", elements="str", required=True),
        state=dict(type="str", choices=["present", "absent", "exists", "enforced"], default="present"),
    )

    module = AAPModule(argument_spec=argument_spec, supports_check_mode=True)
    AAPRoleDefinition(module).manage()


if __name__ == "__main__":
    main()
