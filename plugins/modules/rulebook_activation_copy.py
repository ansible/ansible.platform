#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/rulebook_activation_copy.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: rulebook_activation_copy
author: Red Hat (@RedHatOfficial)
short_description: Copy rulebook activations in EDA controller
description:
  - Copy an existing rulebook activation in the EDA Controller.
  - This module uses the persistent connection manager for improved performance.
version_added: "2.6.0"

options:
  name:
    description:
      - The name for the new copied rulebook activation.
    required: true
    type: str

  copy_from:
    description:
      - Name of the existing rulebook activation to copy.
    required: true
    type: str

  state:
    description:
      - Desired state of the resource.
    type: str
    choices: ["present"]
    default: "present"

seealso:
  - module: ansible.eda.rulebook_activation_copy

extends_documentation_fragment:
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Copy an existing rulebook activation
  ansible.platform.rulebook_activation_copy:
    name: "Example Rulebook Activation - copy"
    copy_from: "Example Rulebook Activation"
...
"""

RETURN = """
id:
  description: ID of the new rulebook activation copy.
  returned: when successful
  type: int
  sample: 42

changed:
  description: Whether the resource was changed.
  returned: always
  type: bool

rulebook_activation_copy:
  description: The copied rulebook activation resource.
  returned: when successful
  type: dict
  contains:
    id:
      description: Numeric database ID of the activation.
      type: int
    name:
      description: Name of the activation.
      type: str
...
"""
