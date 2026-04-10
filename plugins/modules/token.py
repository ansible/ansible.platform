#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2020, John Westcott IV <john.westcott.iv@redhat.com>
# (c) 2021, Sean Sullivan <@sean-m-sullivan>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: token
author: "John Westcott IV (@john-westcott-iv), Sean Sullivan (@sean-m-sullivan)"
short_description: create, update, or destroy automation platform gateway tokens.
description:
    - Create or destroy automation platform gateway tokens.
    - In addition, the module sets an Ansible fact which can be passed into other
      aap modules as the parameter aap_token. See examples for usage.
    - Because of the sensitive nature of tokens, the created token value is only available once
      through the Ansible fact. (See RETURN for details)
    - Due to the nature of tokens in automation platform gateway this module is not idempotent. A second will
      with the same parameters will create a new token.
    - If you are creating a temporary token for use with modules you should delete the token
      when you are done with it. See the example for how to do it.
options:
    application:
      description:
        - The application name, ID, or named URL tied to this token.
      required: False
      type: str
    description:
      description:
        - Optional description of this access token.
      required: False
      type: str
    organization:
      description:
        - Organization name, ID, or named URL the application exists in if applicable
        - Used to help lookup the object, cannot be modified using this module.
        - If not provided, will lookup by name only, which does not work with duplicates.
      type: str
    existing_token:
      description: The data structure produced from token in create mode to be used with state absent.
      type: dict
    existing_token_id:
      description: A token ID (number) which can be used to delete an arbitrary token with state absent.
      type: str
    scope:
      description:
        - Allowed scopes, further restricts user's permissions.
        - "Acceptable values are: 'read', 'write', 'openid', 'roles'."
        - Multiple scopes can be provided as a list to combine them (e.g. openid + roles for OIDC identity and role claims).
        - A single scope can also be provided as a string for convenience.
      required: False
      type: list
      elements: str
      choices: ["read", "write", "openid", "roles"]
    state:
      description:
        - Desired state of the resource.
      choices: ["present", "absent"]
      default: "present"
      type: str

extends_documentation_fragment: ansible.platform.auth
"""

EXAMPLES = """
- block:
    - name: Create a new token using an existing token
      ansible.platform.token:
        description: '{{ token_description }}'
        scope: "write"
        state: present
        aap_token: "{{ my_existing_token }}"

    - name: Delete this token
      ansible.platform.token:
        existing_token: "{{ aap_token }}"
        state: absent

    - name: Create a new token using username/password
      ansible.platform.token:
        description: '{{ token_description }}'
        scope: "write"
        state: present
        aap_hostname: "{{ aap_gateway }}"
        aap_username: "{{ my_username }}"
        aap_password: "{{ my_password }}"

    - name: Use our new token to make another call
      ansible.builtin.set_fact:
        aap_token: "{{ aap_token }}"

  always:
    - name: Delete our Token with the token we created
      ansible.platform.token:
        existing_token: "{{ aap_token }}"
        state: absent
      when: token is defined

- name: Create a token with openid and roles scopes for OIDC
  ansible.platform.token:
    description: 'OIDC token'
    scope:
      - openid
      - roles
    state: present

- name: Delete a token by its id
  ansible.platform.token:
    existing_token_id: 4
    state: absent
...
"""

RETURN = """
aap_token:
  type: dict
  description: An Ansible Fact variable representing a token object which can be used for auth in subsequent modules. See examples for usage.
  contains:
    token:
      description: The token that was generated. This token can never be accessed again, make sure this value is noted before it is lost.
      type: str
    id:
      description: The numeric ID of the token created
      type: str
  returned: on successful create
"""
