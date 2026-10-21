#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: bulk_host_delete
author: "Ansible Platform Collection Contributors"
short_description: Bulk delete hosts in Controller.
description:
    - Delete multiple hosts in a single API request to Controller.
    - Accepts a list of host IDs and removes them all at once.
options:
    hosts:
        description:
            - List of host IDs to delete.
        required: true
        type: list
        elements: int
seealso:
    - module: ansible.controller.bulk_host_delete
    - module: awx.awx.bulk_host_delete
extends_documentation_fragment: ansible.platform.auth
version_added: "2.8.0"
"""

EXAMPLES = """
- name: Bulk delete hosts by ID
  ansible.platform.bulk_host_delete:
    hosts:
      - 1
      - 2
      - 3

- name: Delete hosts gathered from a query
  ansible.platform.bulk_host_delete:
    hosts: "{{ host_ids_to_remove }}"
"""

RETURN = """
changed:
    description: Whether any hosts were deleted.
    returned: success
    type: bool
    sample: true
"""
