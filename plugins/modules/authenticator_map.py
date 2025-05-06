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
- name: "Create LDAP authentication map"
    vars:
      platform_maps:
        - name: "Global Super Admins"
          authenticator: "LDAPAuth"
          revoke: true
          map_type: is_superuser
          triggers:
            groups:
              has_and:
                - "cn=aap-admins,cn=groups,cn=accounts,dc=example,dc=com"
          order: 0
        - name: "Prod-HR-CaaC-Admins-MAP-ORG"
          authenticator: "LDAPAuth"
          revoke: true
          map_type: organization
          role: Organization Admin
          organization: "Prod-HR-CaaC"
          team: prod-hr-team-admins
          triggers:
            groups:
              has_and:
                - "cn=prod-hr-admins,cn=groups,cn=accounts,dc=example,dc=com"
          order: 1
        - name: "Prod-HR-CaaC-Users-MAP-ORG"
          authenticator: "LDAPAuth"
          revoke: true
          map_type: organization
          role: Organization Member
          organization: "Prod-HR-CaaC"
          team: prod-hr-team-users
          triggers:
            groups:
              has_and:
                - "cn=prod-hr-users,cn=groups,cn=accounts,dc=example,dc=com"
          order: 1
        - name: "Prod-IT-CaaC-Admins-MAP-ORG"
          authenticator: "LDAPAuth"
          revoke: true
          map_type: organization
          role: Organization Admin
          organization: "Prod-IT-CaaC"
          team: prod-it-team-admins
          triggers:
            groups:
              has_and:
                - "cn=prod-it-admins,cn=groups,cn=accounts,dc=example,dc=com"
          order: 1
        - name: "Prod-IT-CaaC-Users-MAP-ORG"
          authenticator: "LDAPAuth"
          revoke: true
          map_type: organization
          role: Organization Member
          organization: "Prod-IT-CaaC"
          team: prod-it-team-users
          triggers:
            groups:
              has_and:
                - "cn=prod-it-users,cn=groups,cn=accounts,dc=example,dc=com"
          order: 1
        - name: "Prod-HR-CaaC-Admins-MAP-Team"
          authenticator: "LDAPAuth"
          revoke: true
          map_type: team
          role: Team Admin
          organization: "Prod-HR-CaaC"
          team: prod-hr-team-admins
          triggers:
            groups:
              has_and:
                - "cn=prod-hr-admins,cn=groups,cn=accounts,dc=example,dc=com"
          order: 2
        - name: "Prod-HR-CaaC-Users-MAP-Team"
          authenticator: "LDAPAuth"
          revoke: true
          map_type: team
          role: Team Member
          organization: "Prod-HR-CaaC"
          team: prod-hr-team-users
          triggers:
            groups:
              has_and:
                - "cn=prod-hr-users,cn=groups,cn=accounts,dc=example,dc=com"
          order: 2
        - name: "Prod-IT-CaaC-Admins-MAP-Team"
          authenticator: "LDAPAuth"
          revoke: true
          map_type: team
          role: Team Admin
          organization: "Prod-IT-CaaC"
          team: prod-it-team-admins
          triggers:
            groups:
              has_and:
                - "cn=prod-it-admins,cn=groups,cn=accounts,dc=example,dc=com"
          order: 2
        - name: "Prod-IT-CaaC-Users-MAP-Team"
          authenticator: "LDAPAuth"
          revoke: true
          map_type: team
          role: Team Member
          organization: "Prod-IT-CaaC"
          team: prod-it-team-users
          triggers:
            groups:
              has_and:
                - "cn=prod-it-users,cn=groups,cn=accounts,dc=example,dc=com"
          order: 2
    ansible.platform.authenticator_map:       
      name: "{{ __platform_authenticator_maps_item.name | mandatory }}"
      new_name: "{{ __platform_authenticator_maps_item.new_name | default(omit) }}"
      authenticator: "{{ __platform_authenticator_maps_item.authenticator | default(omit) }}"
      new_authenticator: "{{ __platform_authenticator_maps_item.new_authenticator | default(omit) }}"
      revoke: "{{ __platform_authenticator_maps_item.revoke | default(omit) }}"
      map_type: "{{ __platform_authenticator_maps_item.map_type | default(omit) }}"
      team: "{{ __platform_authenticator_maps_item.team | default(omit) }}"
      organization: "{{ __platform_authenticator_maps_item.organization | default(omit) }}"
      role: "{{ __platform_authenticator_maps_item.role | default(omit) }}"
      triggers: "{{ __platform_authenticator_maps_item.triggers | default(omit) }}"
      order: "{{ __platform_authenticator_maps_item.order | default(omit) }}"
      state: "{{ __platform_authenticator_maps_item.state | default(gateway_state | default(omit, true)) }}"
      # Role Standard Options
      gateway_config_file: "{{ gateway_config_file | default(omit, true) }}"
      gateway_hostname: "{{ gateway_hostname | default(omit, true) }}"
      gateway_password: "{{ gateway_password | default(omit, true) }}"
      gateway_username: "{{ gateway_username | default(omit, true) }}"
      gateway_token: "{{ gateway_token | default(omit, true) }}"
      gateway_request_timeout: "{{ gateway_request_timeout | default(omit, true) }}"
      gateway_validate_certs: "{{ gateway_validate_certs | default(omit) }}"
    # controller_settings must be either a dictionary/mapping or a list of dictionaries
    loop: "{{ platform_authenticator_maps is mapping | ternary([platform_authenticator_maps], platform_authenticator_maps) }}"
    loop_control:
      loop_var: __platform_authenticator_maps_item
...
"""

from ..module_utils.aap_authenticator_map import AAPAuthenticatorMap  # noqa
from ..module_utils.aap_module import AAPModule  # noqa


def main():
    argument_spec = dict(
        name=dict(type="str", required=True),
        new_name=dict(type="str"),
        authenticator=dict(type="str", required=True),
        new_authenticator=dict(type="str"),
        revoke=dict(type="bool", default=False),
        map_type=dict(type="str", choices=["allow", "is_superuser", "team", "organization", "role"]),
        team=dict(type="str"),
        role=dict(type="str"),
        organization=dict(type="str"),
        triggers=dict(type="dict"),
        order=dict(type="int"),
        state=dict(choices=["present", "absent", "exists", "enforced"], default="present"),
    )

    # Create a module with spec
    module = AAPModule(argument_spec=argument_spec, supports_check_mode=True)

    AAPAuthenticatorMap(module).manage()


if __name__ == "__main__":
    main()
