#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2019, John Westcott IV <john.westcott.iv@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: subscriptions
author: "John Westcott IV (@john-westcott-iv)"
short_description: Get subscription list
description:
    - Get subscriptions available to Automation Platform Controller.
    - The credentials you use will be stored for future use in retrieving
      renewal or expanded subscriptions.
options:
    username:
      description:
        - Red Hat username to get available subscriptions.
      required: False
      type: str
    password:
      description:
        - Red Hat password to get available subscriptions.
      required: False
      type: str
    client_id:
      description:
        - Red Hat service account client ID to get available subscriptions.
      required: False
      type: str
    client_secret:
      description:
        - Red Hat service account client secret to get available subscriptions.
      required: False
      type: str
    filters:
      description:
        - Client side filters to apply to the subscriptions.
        - For any entries in this dict, if there is a corresponding entry in the
          subscription it must contain the value from this dict.
        - Note this is a client side search, not an API side search.
      required: False
      type: dict
      default: {}

mutually_exclusive:
  - ['username', 'client_id']

required_together:
  - ['username', 'password']
  - ['client_id', 'client_secret']

required_one_of:
  - ['username', 'client_id']

extends_documentation_fragment: ansible.platform.auth
"""

EXAMPLES = """
- name: Get subscriptions with service account
  ansible.platform.subscriptions:
    client_id: "00000000-0000-0000-0000-000000000000"
    client_secret: "your-client-secret-here"

- name: Get subscriptions with username and password
  ansible.platform.subscriptions:
    username: "my_username"
    password: "my_password"

- name: Get subscriptions with a filter
  ansible.platform.subscriptions:
    client_id: "00000000-0000-0000-0000-000000000000"
    client_secret: "your-client-secret-here"
    filters:
      product_name: "Red Hat Ansible Automation Platform"
      support_level: "Self-Support"
...
"""

RETURN = """
subscriptions:
    description: List of subscription dictionaries matching the filters.
    returned: If login succeeded
    type: list
    elements: dict
"""
