#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2019, John Westcott IV <john.westcott.iv@redhat.com>
# Copyright: (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/subscriptions.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: subscriptions
author: Red Hat (@RedHatOfficial)
short_description: Get available subscriptions from Red Hat
description:
  - Retrieve subscriptions available to Automation Platform Controller.
  - The credentials you provide will be used to authenticate with Red Hat
    and retrieve available subscriptions.
  - This module uses the persistent connection manager for improved performance.
version_added: "1.0.0"

options:
  username:
    description:
      - Red Hat username to get available subscriptions.
    required: false
    type: str

  password:
    description:
      - Red Hat password to get available subscriptions.
    required: false
    type: str

  client_id:
    description:
      - Red Hat service account client ID to get available subscriptions.
    required: false
    type: str

  client_secret:
    description:
      - Red Hat service account client secret to get available subscriptions.
    required: false
    type: str

  filters:
    description:
      - Client-side filters to apply to the subscriptions.
      - For any entries in this dict, if there is a corresponding entry in
        the subscription it must contain the value from this dict.
      - This is a client-side search, not an API-side search.
    required: false
    type: dict
    default: {}

mutually_exclusive:
  - ['username', 'client_id']

required_together:
  - ['username', 'password']
  - ['client_id', 'client_secret']

required_one_of:
  - ['username', 'client_id']

extends_documentation_fragment:
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Get subscriptions with service account
  ansible.platform.subscriptions:
    client_id: "00000000-0000-0000-0000-000000000000"
    client_secret: "your-client-secret-here"
  register: subs

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
"""

RETURN = """
changed:
  description: Always false since this module only retrieves data.
  returned: always
  type: bool

subscriptions:
  description: List of subscriptions matching the provided filters.
  returned: success
  type: list
  elements: dict
"""
