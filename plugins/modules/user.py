#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2020, John Westcott IV <john.westcott.iv@redhat.com>
# (c) 2023, Sean Sullivan <@sean-m-sullivan>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/user.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: user
author: Sean Sullivan (@sean-m-sullivan)
short_description: Manage gateway users
description:
  - Create, update, or delete users in Ansible Automation Platform Gateway
version_added: "1.0.0"

options:
  organizations:
    description:
      - B(Deprecated)
      - This option is deprecated and will be removed in a release after 2026-05-20.
      - For associating a user to an organization, please use the ansible.platform.role_user_assignment module.
      - HORIZONTALLINE
      - List of organization names or IDs to associate with the user.
      - Organizations must already exist - the module will not create missing organizations.
      - If any specified organization doesn't exist, the operation will fail.
    type: list
    elements: str

  is_platform_auditor:
    description:
      - B(Deprecated)
      - This option is deprecated and will be removed in a release after 2026-05-20.
      - For designating a user as an auditor, please use the ansible.platform.role_user_assignment module.
      - HORIZONTALLINE
      - Designates that this user is a platform auditor.
    type: bool
    aliases: ['auditor']

  username:
    description:
      - Username for the user
      - Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.
    required: true
    type: str

  email:
    description:
      - Email address of the user
    type: str

  first_name:
    description:
      - First name of the user
    type: str

  last_name:
    description:
      - Last name of the user
    type: str

  password:
    description:
      - Password for the user
      - Write-only field used to set or change the password
    type: str

  is_superuser:
    description:
      - Whether this user has superuser privileges
      - Grants all permissions without explicitly assigning them
    type: bool
    aliases: ['superuser']

  associated_authenticators:
    description:
      - Map of authenticator id to user attributes (uid, email) for that authenticator
      - Keys are authenticator IDs (integer); values are dicts with I(uid) and optionally I(email)
    type: dict

  update_secrets:
    description:
      - When C(false), secret fields (e.g. I(password)) will not be sent during updates,
        preventing false C(changed) reports when the current value cannot be read back.
      - Set to C(true) (default) to always push secrets.
    type: bool
    default: true

  authenticators:
    description:
      - B(Deprecated)
      - This option is deprecated and will be removed in a release after 2026-05-20.
      - For associating a user with authenticators, please use the associated_authenticators option.
      - HORIZONTALLINE
      - A list of authenticators to associate the user with
    type: list
    elements: int

  authenticator_uid:
    description:
      - B(Deprecated)
      - This option is deprecated and will be removed in a release after 2026-05-20.
      - For specifying UIDs per authenticator, please use the associated_authenticators option.
      - HORIZONTALLINE
      - The UID to associate with this user's authenticators
    type: str

  state:
    description:
      - Desired state of the user (CRUD-aligned).
      - C(present) ensures the user exists (create or update); idempotent.
      - C(absent) removes the user; idempotent if already absent.
      - C(exists) reads and returns the current user (no change).
      - C(enforced) ensures the user exists and merges task keys into existing, defaulting any option not provided.
    type: str
    choices: ['present', 'absent', 'exists', 'enforced']
    default: 'present'

extends_documentation_fragment:
  - ansible.platform.auth
  - ansible.platform.state

notes:
  - This module uses a persistent connection manager for improved performance
  - Multiple tasks in a playbook will reuse the same connection
  - For C(exists), only I(username) is required; returns current state (read-only, no change)
  - For C(enforced), omitted fields are left unchanged on the server (merge semantics)

"""

EXAMPLES = """
# ---------------------------------------------------------------------------
# Basic lifecycle
# ---------------------------------------------------------------------------

- name: Create a user
  ansible.platform.user:
    username: jdoe
    first_name: Jane
    last_name: Doe
    email: jdoe@example.com
    password: "{{ vault_jdoe_password }}"
    state: present
  register: created_user

- name: Idempotent re-run — no change expected
  ansible.platform.user:
    username: jdoe
    first_name: Jane
    last_name: Doe
    email: jdoe@example.com
    state: present

# ---------------------------------------------------------------------------
# Round-trip: feed the returned resource dict straight back as input.
# 'state' is omitted intentionally — it defaults to 'present'.
# 'password' will be "Password Disabled" which the module ignores on update.
# ---------------------------------------------------------------------------

- name: Round-trip update using registered result
  ansible.platform.user: "{{ created_user.user | combine({'email': 'jdoe-updated@example.com'}) }}"

# ---------------------------------------------------------------------------
# Privilege escalation
# ---------------------------------------------------------------------------

- name: Grant superuser privileges
  ansible.platform.user:
    username: jdoe
    is_superuser: true

- name: Revoke superuser privileges
  ansible.platform.user:
    username: jdoe
    is_superuser: false

# ---------------------------------------------------------------------------
# Reference a user by numeric id (returned in result.user.id)
# ---------------------------------------------------------------------------

- name: Update user by id
  ansible.platform.user:
    username: "{{ created_user.user.id }}"
    first_name: Janet

# ---------------------------------------------------------------------------
# Read current state without making changes
# ---------------------------------------------------------------------------

- name: Check whether a user exists
  ansible.platform.user:
    username: jdoe
    state: exists
  register: user_check

- name: Show result
  ansible.builtin.debug:
    msg: "User exists: {{ user_check.exists }}"

# ---------------------------------------------------------------------------
# Password handling — set once, skip re-push on subsequent runs
# ---------------------------------------------------------------------------

- name: Create user and skip password re-push on updates
  ansible.platform.user:
    username: jdoe
    password: "{{ vault_jdoe_password }}"
    update_secrets: false
    state: present

# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

- name: Remove a user (idempotent — safe to run even if already absent)
  ansible.platform.user:
    username: jdoe
    state: absent
...
"""

RETURN = """
changed:
  description: Whether any change was made to the resource.
  returned: always
  type: bool
  sample: true

user:
  description: >
    Pure resource configuration returned by the gateway API, filtered to the
    fields this module accepts as input.  The dict can be passed back directly
    as task parameters for idempotent round-trip operation.

    Fields intentionally excluded:

    - C(state) — an Ansible orchestration directive, not resource data.
      Omitting it is safe because C(state) defaults to C(present).

    - C(created), C(modified), C(url) — API read-only timestamps/links that
      are not accepted as module input and would cause validation errors if
      round-tripped blindly.

    The one exception to "argspec-only" is C(id): it is not an input argspec
    field but is included because it is the stable numeric identifier needed
    by subsequent tasks (e.g. C(ansible.platform.role_user_assignment)).
  returned: when the user exists after the task (state != absent)
  type: dict
  contains:
    id:
      description: Numeric primary key assigned by the gateway.
      type: int
      sample: 591
    username:
      description: The login username — the natural lookup key for this resource.
      type: str
      sample: direct-user2
    email:
      description: Email address of the user.
      type: str
      sample: user@example.com
    first_name:
      description: First name.
      type: str
      sample: Jane
    last_name:
      description: Last name.
      type: str
      sample: Doe
    is_superuser:
      description: Whether the user has superuser privileges.
      type: bool
      sample: false
    password:
      description: >
        Always returned as C(Password Disabled) because the gateway API never
        echoes passwords.  Passing this value back as C(password) input is safe
        — the module skips the password field when the value equals
        C(Password Disabled).
      type: str
      sample: "Password Disabled"
    associated_authenticators:
      description: >
        Map of authenticator ID (integer key as string) to user attributes
        (uid, email) for that authenticator.
      type: dict
      sample: {}
...
"""
