#!/usr/bin/python
# coding: utf-8 -*-
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
DOCUMENTATION = """
---
module: notification_template
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller notification templates
description:
  - Create, update, or delete notification templates on Ansible Automation Platform Controller.
version_added: "2.8.0"
options:
  name:
    description: The name of the notification template.
    required: true
    type: str
  new_name:
    description: Setting this option will change the existing name.
    type: str
  description:
    description: The description of the notification template.
    type: str
  organization:
    description: Organization name or ID the notification template belongs to.
    required: true
    type: str
  notification_type:
    description: The type of notification to be sent.
    choices: [awssns, email, grafana, irc, mattermost, pagerduty, rocketchat, slack, twilio, webhook]
    type: str
  notification_configuration:
    description: The notification configuration as a dictionary.
    type: dict
  messages:
    description: Optional custom messages for the notification template.
    type: dict
seealso:
  - module: ansible.controller.notification_template
  - module: awx.awx.notification_template
extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
...
"""
EXAMPLES = """
- name: Create a webhook notification template
  ansible.platform.notification_template:
    name: "Deploy Webhook"
    organization: "Default"
    notification_type: webhook
    notification_configuration:
      url: "https://example.com/webhook"
      http_method: "POST"
      headers: {}
    state: present
...
"""
RETURN = """
changed:
  description: Whether the notification template was created, updated, or deleted.
  returned: always
  type: bool
notification_template:
  description: The notification template resource.
  returned: when state is present, exists, or enforced
  type: dict
...
"""
