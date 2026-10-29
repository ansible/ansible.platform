#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2020, Ansible by Red Hat, Inc
# Copyright: (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/controller_meta.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: controller_meta
author: Red Hat (@RedHatOfficial)
short_description: Returns metadata about the collection this module lives in.
description:
  - Allows a user to find out what collection this module exists in.
  - This takes common module parameters, but does nothing with them.
  - Useful for dynamically constructing lookup plugin references without
    hard-coding the collection name.
version_added: "2.7.0"

options: {}

extends_documentation_fragment:
  - ansible.platform.auth

seealso:
  - module: ansible.controller.controller_meta
  - module: awx.awx.controller_meta
"""

EXAMPLES = """
- name: Get collection metadata
  ansible.platform.controller_meta:
  register: result

- name: Show details about the collection
  ansible.builtin.debug:
    var: result

- name: Use the prefix to dynamically reference a lookup plugin
  ansible.builtin.debug:
    msg: "{{ lookup(result.prefix + '.gateway_api', 'settings/ui') }}"
...
"""

RETURN = """
prefix:
    description: Collection namespace and name in the namespace.name format.
    returned: success
    sample: ansible.platform
    type: str
name:
    description: Collection name.
    returned: success
    sample: platform
    type: str
namespace:
    description: Collection namespace.
    returned: success
    sample: ansible
    type: str
version:
    description: Version of the collection.
    returned: success
    sample: 2.7.0
    type: str
...
"""
