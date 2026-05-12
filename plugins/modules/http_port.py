#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2024, Martin Slemr <@slemrmartin>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: http_port
author: Martin Slemr (@slemrmartin)
short_description: Configure a gateway http port.
description:
    - Configure an automation platform gateway http ports where Envoy proxy listens.
options:
    name:
      required: true
      type: str
      description: The name of the http port, must be unique
    new_name:
      type: str
      description: Setting this option will change the existing name (looked up via the name field)
    number:
      type: int
      description:
        - Port number, must be unique
        - Required when creating new Http Port
    use_https:
      default: false
      type: bool
      description: Secure this port with HTTPS
    is_api_port:
      default: false
      type: bool
      description:
        - If true, port is used for serving remote AAP APIs.
        - Only one can be set to True

extends_documentation_fragment:
- ansible.platform.state
- ansible.platform.auth
"""

EXAMPLES = """
- name: Add API http port
  ansible.platform.http_port:
    name: "Port for APIs"
    number: 443
    use_https: true
    is_api_port: true
    state: present

- name: Remove API http port
  ansible.platform.http_port:
    name: "Port for APIs"
    state: absent

- name: Update http port
  ansible.platform.http_port:
    name: "Port for APIs"
    number: 80
    use_https: false
...
"""

# This module is doc-only; the action plugin runs all logic via the manager.
