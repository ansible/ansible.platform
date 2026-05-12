"""
Legacy: DOCUMENTATION for the user module now lives in plugins/modules/user.py.

The action plugin discovers it via _get_documentation() from the sibling module
(meraki_rm-style). This file is kept for reference only; do not import from here.
"""

DOCUMENTATION = """
---
module: user
author: Sean Sullivan (@sean-m-sullivan)
short_description: Manage gateway users
description:
  - Create, update, or delete users in Ansible Automation Platform Gateway
  - This module uses the persistent connection manager for improved performance
version_added: "1.0.0"

options:
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
    no_log: true

  is_superuser:
    description:
      - Whether this user has superuser privileges
      - Grants all permissions without explicitly assigning them
    type: bool
    aliases: ['superuser']

  update_secrets:
    description:
      - When C(false), secret fields (e.g. I(password)) will not be sent during updates,
        preventing false C(changed) reports when the current value cannot be read back.
      - Set to C(true) (default) to always push secrets.
    type: bool
    default: true

  authenticators:
    description:
      - List of authenticator IDs to associate with the user
      - Deprecated - use I(associated_authenticators) instead
    type: list
    elements: int

  authenticator_uid:
    description:
      - UID for authenticator association
      - Deprecated - use I(associated_authenticators) instead
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

return:
  user:
    description: User resource (when state is not C(absent)); matches argspec + read-only fields (id, url, created, modified).
  before:
    description: State before the operation (when state is C(enforced) or C(absent) and resource existed).
  after:
    description: State after the operation (when a change was made).
  changed:
    description: Whether a change was made.
"""
