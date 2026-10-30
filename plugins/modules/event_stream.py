#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/event_stream.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: event_stream
author: Red Hat (@RedHatOfficial)
short_description: Manage event streams in EDA controller
description:
  - Create, update, or delete event streams in EDA controller.
  - Event streams allow external systems to send events to EDA controller
    for processing by rulebook activations.
  - This module uses the persistent connection manager for improved performance.
version_added: "2.6.0"

options:
  name:
    description:
      - Name of the event stream.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (lookup via O(name)).
    type: str

  credential_name:
    description:
      - The name of the credential to associate with this event stream.
      - The credential type must be one of the supported event stream credential types
        (e.g. 'HMAC Event Stream', 'Basic Event Stream', 'Token Event Stream',
        'GitHub Event Stream', etc.).
      - Required when O(state=present).
    type: str
    aliases:
      - credential

  organization_name:
    description:
      - The name of the organization this event stream belongs to.
      - Required when O(state=present).
    type: str
    aliases:
      - organization

  event_stream_type:
    description:
      - Type of the event stream.
      - This field is not necessary to create an event stream and will be ignored.
      - B(Deprecated), will be removed in version 3.0.0.
    type: str
    aliases:
      - type

  headers:
    description:
      - Comma separated HTTP header keys that you want to include in the event payload.
      - To include all headers in the event payload, leave the field empty.
    type: str

  forward_events:
    description:
      - Enable the event stream to forward events to the rulebook activation where it is configured.
    type: bool

  uuid:
    description:
      - Custom UUID for the event stream URL.
      - If not provided, a UUID will be auto-generated.
      - Must be a valid UUID format and unique across all event streams.
    type: str

  state:
    description:
      - Desired state of the resource.
      - C(present) creates the event stream if it does not exist, or updates it if it does.
      - C(absent) removes the event stream if it exists.
      - C(exists) checks whether the event stream exists without making changes.
      - C(enforced) ensures the event stream matches the declared fields exactly.
    type: str
    choices: ["present", "absent", "exists", "enforced"]
    default: "present"

seealso:
  - module: ansible.eda.event_stream

extends_documentation_fragment:
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Create an EDA event stream
  ansible.platform.event_stream:
    name: "Example Event Stream"
    credential_name: "Example Credential"
    organization_name: Default
    state: present

- name: Create an event stream with custom UUID and forwarding enabled
  ansible.platform.event_stream:
    name: "Static Event Stream"
    uuid: "550e8400-e29b-41d4-a716-446655440000"
    credential_name: "Example Credential"
    organization_name: Default
    forward_events: true
    headers: "Content-Type,X-Custom-Header"
    state: present

- name: Rename an event stream
  ansible.platform.event_stream:
    name: "Example Event Stream"
    new_name: "Renamed Event Stream"
    credential_name: "Example Credential"
    organization_name: Default
    state: present

- name: Delete an EDA event stream
  ansible.platform.event_stream:
    name: "Example Event Stream"
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the event stream was created, updated, or deleted.
  returned: always
  type: bool

id:
  description: Numeric database ID of the event stream.
  returned: when state is present and successful
  type: int

event_stream:
  description: The event stream resource as it exists after the operation.
  returned: when state is present and successful
  type: dict
  contains:
    id:
      description: Numeric database ID of the event stream.
      type: int
    name:
      description: Name of the event stream.
      type: str
    uuid:
      description: UUID for the event stream URL.
      type: str
...
"""
