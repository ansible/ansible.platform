#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2024, Martin Slemr <@slemrmartin>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: authenticator_map
author: Red Hat (@RedHatOfficial)
short_description: Configure a gateway authenticator maps.
description:
    - Configure an automation platform gateway authenticator maps.
options:
    name:
      required: true
      type: str
      description: The name of the authenticator mapping, must be unique
    new_name:
      type: str
      description: Setting this option will change the existing name (looked up via the name field)
    authenticator:
      type: str
      required: true
      description: The name of ID referencing the Authenticator
    new_authenticator:
      type: str
      description: Setting this option will change the existing authenticator (looked up via the authenticator field)
    revoke:
      type: bool
      default: false
      description: If a user does not meet this rule should we revoke the permission
    map_type:
      type: str
      description:
      - What does the map work on, a team, a user flag or is this an allow rule
      choices: ["allow", "is_superuser", "team", "organization", "role"]
    team:
      type: str
      description:
      - A team name this rule works on
      - required if map_type is a 'team'
      - required if role's content type is a 'team'
    organization:
      type: str
      description:
      - An organization name this rule works on
      - required if map_type is either 'organization' or 'team'
      - required if role's content type is either 'organization' or 'team'
    role:
      type: str
      description:
      - The name of the RBAC Role Definition to be used for this map
    triggers:
      type: dict
      description:
      - Trigger information for this rule
      - django-ansible-base/ansible_base/authentication/utils/trigger_definition.py
    order:
      type: int
      description:
      - The order in which this rule should be processed, smaller numbers are of higher precedence
      - Items with the same order will be executed in random order
      - Value must be greater or equal to 0
      - Defaults to 0 (by API)
extends_documentation_fragment:
- ansible.platform.state
- ansible.platform.auth
"""

EXAMPLES = """
- name: Create LDAP authentication map - Global Super Admins
  ansible.platform.authenticator_map:
    name: "Global Super Admins"
    authenticator: "LDAPAuth"
    revoke: true
    map_type: is_superuser
    triggers:
      groups:
        has_and:
          - "cn=aap-admins,cn=groups,cn=accounts,dc=example,dc=com"
    order: 0
    state: present

- name: Create LDAP authentication map - Prod-HR-CaaC-Admins-MAP-ORG
  ansible.platform.authenticator_map:
    name: "Prod-HR-CaaC-Admins-MAP-ORG"
    authenticator: "LDAPAuth"
    revoke: true
    map_type: organization
    organization: "Prod-HR"
    role: "CaaC Admins"
    order: 2
    state: present
...
"""

# This module is doc-only; the action plugin runs all logic via the manager.
