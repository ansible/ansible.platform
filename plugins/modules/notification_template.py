#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2018, Samuel Carpentier <samuelcarpentier0@gmail.ca>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/notification_template.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: notification_template
author: Red Hat (@RedHatOfficial)
short_description: Create, update, or destroy Automation Platform Controller notification templates
description:
  - Create, update, or destroy Automation Platform Controller notification templates.
version_added: "3.0.0"

options:
  name:
    description:
      - The name of the notification template.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  copy_from:
    description:
      - Name or ID to copy the notification template from.
      - This will copy an existing notification template and change any parameters supplied.
      - The new notification template name will be the one provided in the C(name) parameter.
      - The organization parameter is not used in this, to facilitate copy from one organization to another.
    type: str

  description:
    description:
      - The description of the notification template.
    type: str

  organization:
    description:
      - The organization name, ID, or named URL the notification template belongs to.
    type: str

  notification_type:
    description:
      - The type of notification to be sent.
    choices:
      - awssns
      - email
      - grafana
      - irc
      - mattermost
      - pagerduty
      - rocketchat
      - slack
      - twilio
      - webhook
    type: str

  notification_configuration:
    description:
      - The notification configuration file. Contents vary by C(notification_type) — see the
        Automation Platform Controller documentation for the fields each type accepts.
    type: dict

  messages:
    description:
      - Optional custom messages for the notification template.
    type: dict

  state:
    description:
      - Desired state of the notification template.
      - C(present) ensures the notification template exists (create or update); idempotent.
      - C(absent) removes the notification template; idempotent if already absent.
      - C(exists) reads and returns the current notification template (no change).
    type: str
    choices: ['present', 'absent', 'exists', 'enforced']
    default: 'present'

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth

seealso:
  - module: ansible.controller.notification_template
  - module: awx.awx.notification_template
"""

EXAMPLES = """
- name: Add Slack notification with custom messages
  ansible.platform.notification_template:
    name: slack notification
    organization: Default
    notification_type: slack
    notification_configuration:
      channels:
        - general
      token: cefda9e2be1f21d11cdd9452f5b7f97fda977f42
    messages:
      started:
        message: "{{ '{{ job_friendly_name }}{{ job.id }} started' }}"
    state: present

- name: Add webhook notification
  ansible.platform.notification_template:
    name: webhook notification
    notification_type: webhook
    notification_configuration:
      url: http://www.example.com/hook
      headers:
        X-Custom-Header: value123
    state: present

- name: Copy a notification template
  ansible.platform.notification_template:
    name: foo notification
    copy_from: email notification
    organization: Foo

- name: Delete notification
  ansible.platform.notification_template:
    name: old notification
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the notification template was created, updated, or deleted.
  returned: always
  type: bool

notification_template:
  description: >
    The notification template resource as it exists after the operation.
    Contains only the fields accepted as module input (argspec fields) plus C(id).
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the notification template.
      type: int
    name:
      description: Name of the notification template.
      type: str
    notification_type:
      description: Type of notification.
      type: str
...
"""
