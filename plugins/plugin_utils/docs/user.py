"""
DOCUMENTATION string for user module.

This serves as the single source of truth for the module's interface.
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

  is_platform_auditor:
    description:
      - Whether this user is a platform auditor
      - Deprecated - use role_user_assignment module instead
    type: bool
    aliases: ['auditor']

  organizations:
    description:
      - List of organization names to associate with the user
      - Organizations must already exist
      - Deprecated - use role_user_assignment module instead
    type: list
    elements: str

  state:
    description:
      - Desired state of the user.
      - C(present) and C(absent) are the classic create/update and delete.
      - C(gathered) reads and returns the current user (no change).
      - C(merged) ensures the user exists and merges task keys into existing (create if missing, else PATCH).
      - C(replaced) makes the task dict the full source of truth (delete then create if existed, else create).
      - C(deleted) removes the user (same as C(absent)).
    type: str
    choices: ['present', 'absent', 'gathered', 'merged', 'replaced', 'deleted']
    default: 'present'

extends_documentation_fragment:
  - ansible.platform.auth
  - ansible.platform.state

notes:
  - This module uses a persistent connection manager for improved performance
  - Multiple tasks in a playbook will reuse the same connection
  - The organizations and is_platform_auditor fields are deprecated
  - For C(gathered), only I(username) is required to identify the user; returns current state (no change)
  - For C(merged), only provided fields are updated; omitted fields are left unchanged on the server
  - For C(replaced), the user is recreated from the task dict; any server-side-only fields are reset

return:
  user:
    description: User resource (when state is not C(absent)/C(deleted)); matches argspec + read-only fields (id, url, created, modified).
  before:
    description: State before the operation (when state is C(merged), C(replaced), C(absent), or C(deleted) and resource existed).
  after:
    description: State after the operation (when a change was made).
  changed:
    description: Whether a change was made.
"""
