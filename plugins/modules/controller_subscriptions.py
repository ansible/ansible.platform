#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: controller_subscriptions
author: "Ansible Platform Collection Contributors"
short_description: Get available subscriptions from Automation Controller.
description:
    - Retrieve subscriptions available to Automation Controller by providing
      Red Hat credentials (username/password or service-account client_id/client_secret).
    - The credentials you supply are stored by Controller for future use in
      retrieving renewal or expanded subscriptions.
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
        - Client side filters to apply to the subscriptions.
        - For any entries in this dict, if there is a corresponding entry in the
          subscription it must contain the value from this dict.
        - This is a client-side search, not an API-side search.
      required: false
      type: dict
      default: {}
extends_documentation_fragment: ansible.platform.auth
"""

EXAMPLES = """
- name: Get subscriptions with service account credentials
  ansible.platform.controller_subscriptions:
    client_id: "00000000-0000-0000-0000-000000000000"
    client_secret: "your-client-secret-here"

- name: Get subscriptions with username and password
  ansible.platform.controller_subscriptions:
    username: "my_username"
    password: "my_password"

- name: Get subscriptions with a filter
  ansible.platform.controller_subscriptions:
    client_id: "00000000-0000-0000-0000-000000000000"
    client_secret: "your-client-secret-here"
    filters:
      product_name: "Red Hat Ansible Automation Platform"
      support_level: "Self-Support"
"""

RETURN = """
subscriptions:
    description: List of subscription objects matching the supplied filters.
    returned: success
    type: list
    elements: dict
"""
