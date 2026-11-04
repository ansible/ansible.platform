#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Manage Automation Controller settings."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: controller_settings
author: Red Hat (@RedHatOfficial)
short_description: Modify Automation Controller settings
description:
  - Modify one or more settings in Automation Controller.
  - The module preserves the legacy C(awx.awx.settings) interface.
  - Use C(name) and C(value) to update one setting, or use C(settings) to update
    several settings at once.
version_added: "2.7.0"

options:
  name:
    description:
      - Name of the Controller setting to modify.
      - Mutually exclusive with C(settings).
    type: str
  value:
    description:
      - Value to set for C(name).
      - String values that look like booleans, integers, lists, or dictionaries
        are converted to their corresponding types before being sent to Controller.
      - Use C(settings) when more precise type control is needed.
    type: str
  settings:
    description:
      - Mapping of Controller setting names to values to update.
      - Mutually exclusive with C(name).
    type: dict

seealso:
  - module: ansible.controller.settings
  - module: awx.awx.settings

extends_documentation_fragment:
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Set one Controller setting
  ansible.platform.controller_settings:
    name: AWX_ISOLATION_BASE_PATH
    value: "/tmp"

- name: Set a boolean Controller setting using the legacy name/value form
  ansible.platform.controller_settings:
    name: AWX_ISOLATION_SHOW_PATHS
    value: "true"

- name: Set several Controller settings with native types
  ansible.platform.controller_settings:
    settings:
      DEFAULT_JOB_TIMEOUT: 3600
      INSIGHTS_TRACKING_STATE: false
      REMOTE_HOST_HEADERS:
        - HTTP_X_FORWARDED_FOR
        - REMOTE_ADDR

- name: Preview a settings change
  ansible.platform.controller_settings:
    name: DEFAULT_JOB_TIMEOUT
    value: "7200"
  check_mode: true
  diff: true
...
"""

RETURN = """
changed:
  description: Whether any requested setting differed and was updated.
  returned: always
  type: bool
old_values:
  description: Values of the requested settings before the operation.
  returned: always
  type: dict
new_values:
  description: Values requested for the operation.
  returned: always
  type: dict
value:
  description: Updated value when the single-setting C(name)/C(value) form is used.
  returned: when name is provided and the update succeeds
  type: raw
values:
  description: Updated values when the bulk C(settings) form is used.
  returned: when settings is provided and the update succeeds
  type: dict
controller_settings:
  description: Controller settings operation details.
  returned: always
  type: dict
...
"""
