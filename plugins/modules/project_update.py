#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/project_update.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: project_update
author: Red Hat (@RedHatOfficial)
short_description: Trigger a Controller project sync
description:
  - Trigger an SCM update for a project on Ansible Automation Platform Controller.
  - Every invocation triggers a new sync; this module is not idempotent.
  - Optionally waits for the sync to complete and reports whether the SCM revision changed.
version_added: "2.8.0"

options:
  name:
    description:
      - Name or ID of the project to update.
    required: true
    type: str
    aliases:
      - project

  organization:
    description:
      - Organization name or ID to scope the project lookup.
      - Used when multiple projects share the same name.
    type: str

  wait:
    description:
      - Wait for the project sync to complete.
      - When true, the module compares the SCM revision before and after the sync
        and reports C(changed=false) if the revision did not change.
    default: true
    type: bool

  interval:
    description:
      - Polling interval in seconds when waiting.
    default: 2.0
    type: float

  timeout:
    description:
      - Maximum seconds to wait before aborting (client-side).
      - Only used when C(wait=true).
    type: int

seealso:
  - module: ansible.controller.project_update
  - module: awx.awx.project_update
  - module: ansible.platform.controller_project

extends_documentation_fragment:
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Update a project and wait for completion
  ansible.platform.project_update:
    name: "My Project"
    timeout: 120

- name: Trigger a project sync without waiting
  ansible.platform.project_update:
    name: "My Project"
    wait: false

- name: Update a project in a specific organization
  ansible.platform.project_update:
    name: "Shared Project Name"
    organization: "Engineering"
    wait: true
...
"""

RETURN = """
id:
  description: ID of the project update job.
  returned: success
  type: int
  sample: 86

status:
  description: Status of the project update.
  returned: success
  type: str
  sample: successful
...
"""
