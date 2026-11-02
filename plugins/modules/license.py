#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2019, John Westcott IV <john.westcott.iv@redhat.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/license.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: license
author: Red Hat (@RedHatOfficial)
short_description: Set or remove the Controller license
description:
  - Apply or remove the license/subscription manifest on Ansible Automation Platform Controller.
  - Supports applying a Red Hat subscription manifest file or attaching by subscription ID.
  - By default, the manifest is only applied if Controller is currently unlicensed or
    trial-licensed. Use C(force=true) to always re-apply.
version_added: "2.8.0"

options:
  manifest:
    description:
      - File path to a Red Hat subscription manifest (a .zip file).
      - Mutually exclusive with C(subscription_id).
      - Required when C(state=present) unless C(subscription_id) is given.
    type: str

  subscription_id:
    description:
      - Red Hat or Red Hat Satellite subscription ID to attach.
      - Mutually exclusive with C(manifest).
      - Requires that subscriptions have been fetched at least once before.
    type: str

  force:
    description:
      - By default, the license manifest is only applied if Controller is currently
        unlicensed or trial-licensed. When C(force=true), the license is always applied.
    type: bool
    default: false

  state:
    description:
      - Desired state of the license.
      - C(present) applies the manifest or subscription.
      - C(absent) removes the current license.
    choices: ['present', 'absent']
    default: present
    type: str

seealso:
  - module: ansible.controller.license
  - module: awx.awx.license
  - module: ansible.platform.subscriptions

extends_documentation_fragment:
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Apply a license manifest
  ansible.platform.license:
    manifest: "/tmp/my_manifest.zip"

- name: Force re-apply a license manifest
  ansible.platform.license:
    manifest: "/tmp/my_manifest.zip"
    force: true

- name: Attach a subscription by ID
  ansible.platform.license:
    subscription_id: "123456"

- name: Remove the license
  ansible.platform.license:
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the license was applied or removed.
  returned: always
  type: bool

license_info:
  description: License information after the operation.
  returned: when state is present
  type: dict
...
"""
