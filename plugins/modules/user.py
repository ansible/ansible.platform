# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later

DOCUMENTATION = r"""
module: user
short_description: Manage Ansible Automation Platform users
description:
  - Ensure a user is present or absent in AAP (via Gateway API) using the internal Platform SDK layer.
  - Supports authentication via environment variables or explicit module parameters.
options:
  username:
    description: User's login name.
    type: str
    required: true
  email:
    description: Email address for the user.
    type: str
  first_name:
    description: First name.
    type: str
  last_name:
    description: Last name.
    type: str
  is_superuser:
    description: Whether the user is a superuser.
    type: bool
    default: false
  state:
    description: Desired state of the user.
    type: str
    choices: [present, absent]
    default: present

  # Optional explicit connection params (fallback to env if omitted)
  base:
    description:
      - AAP base URL (e.g. C(https://aap.example.com)).
      - If omitted, the module will read from C(AAP_BASE) environment variable.
    type: str
  token:
    description:
      - Bearer token used to authenticate to the AAP Gateway.
      - If omitted, the module will read from C(AAP_TOKEN) environment variable.
    type: str
    no_log: true
  verify:
    description:
      - TLS verification setting.
      - Accepts true/false or a filesystem path to a CA bundle (PEM).
      - If omitted, the module reads AAP_VERIFY from the environment.
    type: raw


author:
  - Ansible Platform Team
"""

EXAMPLES = r"""
- name: Ensure a user exists (env-based auth)
  ansible.platform.user:
    username: demo
    email: demo@example.com
    state: present

- name: Ensure a user exists (explicit auth)
  ansible.platform.user:
    username: demo
    email: demo@example.com
    base: "https://aap.example.com"
    token: "{{ lookup('env','AAP_TOKEN') }}"
    verify: false
    state: present

- name: Ensure a user is absent
  ansible.platform.user:
    username: demo
    state: absent

RETURN = r"""
user:
  description: User object after operation (if present).
  returned: always
  type: dict
changed:
  description: Whether any change was made.
  type: bool
  returned: always
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.ansible.platform.plugins.module_utils.platform_sdk import PlatformClient, UsersRepo, User
"""_summary_

  AnsibleModule: helper to parse args, support check_mode, and return exit_json/fail_json.
  SDK imports:
    - PlatformClient: the HTTP client; can run in direct mode or agent proxy mode (persistent).
    - UsersRepo: the repository abstraction that wraps endpoint calls (clean, typed methods).
    - User: the dataclass model for a user (typed object instead of ad-hoc dicts).
"""

import os
import time
import q


def _client_from_params_or_env(module: AnsibleModule) -> PlatformClient:
    """
    Build a PlatformClient from either explicit params (base/token/verify) or AAP_* environment variables.
    Read base, token, verify from module.params. If missing, fall back to os.environ.

    Validate: if base or token is still missing -> module.fail_json(...).
    Normalize verify:
    If it’s a boolean ->  set os.environ['AAP_VERIFY'] to "true" or "false".
    Otherwise, treat it as a path/string ->  set os.environ['AAP_VERIFY'] = <string>.
    Why? Your PlatformClient already reads TLS verify from AAP_VERIFY. Keeping that behavior central avoids drift.
    Define a simple token_provider() that returns (token_value, expiry) with a fixed 1-hour expiry. (Easy to swap later for a real provider from the agent/state-bus.)
    Return PlatformClient(base, token_provider).
    If AAP_AGENT_ADDR is present in the environment (set by your pre_task action), PlatformClient will automatically use agent proxy mode, so all HTTP goes through the persistent agent.
    
    """
    base = module.params.get("base") or os.environ.get("AAP_BASE")
    token_value = module.params.get("token") or os.environ.get("AAP_TOKEN")
    verify = module.params.get("verify")
    if verify is None:
        verify = os.environ.get("AAP_VERIFY", "")

    if not base or not token_value:
        module.fail_json(msg="Missing AAP connection: provide 'base' and 'token' params or set AAP_BASE/AAP_TOKEN environment variables.")

    # PlatformClient reads verify from env var AAP_VERIFY; keep behavior consistent:
    if isinstance(verify, bool):
        os.environ["AAP_VERIFY"] = "true" if verify else "false"
    else:
        # Could be "", or a filesystem path to a PEM file
        os.environ["AAP_VERIFY"] = str(verify)

    def token_provider():
        # simple fixed-expiry (1h); swap with state-bus provider when wiring runtime
        return token_value, time.time() + 3600

    return PlatformClient(base, token_provider)


def run_module():
    q("run user module")
    """
    argument_spec defines the contract the task must satisfy.
    supports_check_mode=True enables --check dry runs, which is crucial for safe CaC.
    no_log: true on token ensures secrets are redacted from logs.
    """ 
    args = dict(
        username=dict(type="str", required=True),
        email=dict(type="str", required=False),
        first_name=dict(type="str", required=False, default=""),
        last_name=dict(type="str", required=False, default=""),
        is_superuser=dict(type="bool", required=False, default=False),
        state=dict(type="str", required=False, default="present", choices=["present", "absent"]),

        # Optional connection parameters (override env if provided)
        base=dict(type="str", required=False),
        token=dict(type="str", required=False, no_log=True),
        verify=dict(type="raw", required=False),
    )

    module = AnsibleModule(argument_spec=args, supports_check_mode=True)

    # "Resolve desired state and build SDK client"
    username = module.params["username"]
    desired_state = module.params["state"]

    try:
        q("get client")
        # build a client
        # UsersRepo.get_by_name() wraps a GET with query params on the AAP API and returns a User model or None.
        client = _client_from_params_or_env(module)
        repo = UsersRepo(client)

        current = repo.get_by_name(username)

        # Absent path
        if desired_state == "absent":
            if module.check_mode:
                module.exit_json(changed=bool(current), user=None)
            if current:
                repo.delete(current)
                module.exit_json(changed=True, user=None)
            module.exit_json(changed=False, user=None)

        # Present path
        # build a desired model
        # Using data class keeps types clean and mirrors the API schema.
        
        desired = User(
            id=current.id if current else None,
            username=username,
            email=module.params.get("email"),
            first_name=module.params.get("first_name") or "",
            last_name=module.params.get("last_name") or "",
            is_superuser=bool(module.params.get("is_superuser")),
        )

        # Create if missing
        if not current:
            if module.check_mode:
                module.exit_json(changed=True, user=desired.__dict__)
            created = repo.create(desired)
            module.exit_json(changed=True, user=created.__dict__)

        # Update (minimal comparison; expand as schema evolves)
        # update if drift exists
        changed = False
        if desired.email and desired.email != current.email:
            changed = True
            current.email = desired.email

        if (
            desired.first_name != current.first_name
            or desired.last_name != current.last_name
            or bool(desired.is_superuser) != bool(current.is_superuser)
        ):
            changed = True
            current.first_name = desired.first_name
            current.last_name = desired.last_name
            current.is_superuser = bool(desired.is_superuser)

        if module.check_mode:
            module.exit_json(changed=changed, user=(current.__dict__ if current else desired.__dict__))

        if changed:
            updated = repo.update(current)
            module.exit_json(changed=True, user=updated.__dict__)
        else:
            module.exit_json(changed=False, user=current.__dict__)

    except Exception as e:
        module.fail_json(msg=str(e))
        
        
#  What makes this “the new approach” (vs older modules)
# Typed models (dataclasses): User is a real model, not an untyped dict. This matches the OpenAPI schema and avoids key typos/shape drift.
# Repositories: UsersRepo hides HTTP details, so module code reads like intent:
# get_by_name, create, update, delete.
# SDK client abstraction: PlatformClient decides transport:
# direct requests.Session() or agent proxy (persistent).
# Idempotency + check mode: explicit change detection, safe dry runs.
# Connection params are normalized: verify is fed back into AAP_VERIFY so the client/agent layer uses a single source of truth.


# How it behaves with your agent
# If your pre_task action started the agent and exported AAP_AGENT_ADDR, then:
# _client_from_params_or_env sets AAP_VERIFY in env,
# PlatformClient.from_env() (or your constructor) sees AAP_AGENT_ADDR,
# All repo calls go through POST /request to the agent,
# The agent uses a single persistent requests.Session with shared token/TLS → fewer handshakes, faster RBAC bulk ops, and central place for locks/caches.

def main():
    run_module()


if __name__ == "__main__":
    main()
