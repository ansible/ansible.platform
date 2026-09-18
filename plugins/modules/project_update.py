#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2020, Sean Sullivan <@sean-m-sullivan>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/project_update.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: project_update
author: Red Hat (@RedHatOfficial)
short_description: Launch a project update (sync)
description:
  - Launch a project update (sync) on the Ansible Automation Platform controller.
  - This module always launches a new project update; it is not idempotent.
version_added: "3.0.0"

options:
  name:
    description:
      - The name of the project to update.
    required: true
    type: str
    aliases:
      - project

  wait:
    description:
      - Wait for the project update to complete.
    default: true
    type: bool

  interval:
    description:
      - The interval in seconds to request an update from the controller.
    default: 2
    type: float

  timeout:
    description:
      - If waiting for the update to complete this will abort after this
        amount of seconds.
      - When C(wait=true) and this option is omitted, polling is capped at
        3600 seconds (1 hour). Set explicitly to use a different limit.
    type: int

extends_documentation_fragment:
  - ansible.platform.auth

notes:
  - The legacy C(organization) option (used only to disambiguate the C(name)
    lookup when project names collide across organizations) is not carried
    over — name lookups resolve globally. Use a unique name, or the numeric
    ID, if this is a concern.

seealso:
  - module: ansible.controller.project_update
  - module: awx.awx.project_update
"""

EXAMPLES = """
- name: Launch a project update with a timeout of 10 seconds
  ansible.platform.project_update:
    name: "Networking Project"
    timeout: 10

- name: Launch a project update without waiting
  ansible.platform.project_update:
    name: "Networking Project"
    wait: false
...
"""

RETURN = """
id:
  description: Project update id of the launched update.
  returned: success
  type: int
  sample: 86

status:
  description:
    - Status of the launched project update.
    - With C(wait=false) this is always C(pending). With C(wait=true) this is
      the terminal status reported by Controller once the update finishes; the
      task fails (C(failed=true)) if that terminal status is C(error),
      C(failed), or C(canceled).
  returned: success
  type: str
  sample: pending
...
"""
