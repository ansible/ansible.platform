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

RETURN =
r"""
# user:
#   description: User object after operation (if present).
#   returned: always
#   type: dict
# changed:
#   description: Whether any change was made.
#   type: bool
#   returned: always
# """

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
import os, sys, datetime

DEBUG_TRACE = os.environ.get("AAP_AGENT_TRACE", "0") == "1"
def trace(msg: str):
    """Uniform trace writer for debugging."""
    if not DEBUG_TRACE:
        return
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[TRACE {ts}] module/user.py: {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        with open("/tmp/aap_agent_debug.log", "a") as f:
            f.write(line + "\n")
    except Exception:
        pass
# -------------------------------------------------------------------

def _client_from_params_or_env(module: AnsibleModule) -> PlatformClient:
    """Build PlatformClient from module params or environment."""
    base = module.params.get("base") or os.environ.get("AAP_BASE")
    token_value = module.params.get("token") or os.environ.get("AAP_TOKEN")
    verify = module.params.get("verify")
    if verify is None:
        verify = os.environ.get("AAP_VERIFY", "")

    # NEW: allow action plugin to pass the agent address explicitly
    agent_addr = module.params.get("agent_addr") or os.environ.get("AAP_AGENT_ADDR")
    if agent_addr:
        os.environ["AAP_AGENT_ADDR"] = agent_addr
        trace(f"using agent_addr={agent_addr}")

    if not base or not token_value:
        module.fail_json(msg="Missing AAP connection: provide 'base' and 'token' or set AAP_BASE/AAP_TOKEN.")

    # normalize verify into env for lower layers
    if isinstance(verify, bool):
        os.environ["AAP_VERIFY"] = "true" if verify else "false"
    else:
        os.environ["AAP_VERIFY"] = str(verify)

    def token_provider():
        return token_value, time.time() + 3600

    trace(f"creating PlatformClient(base={base}, verify={verify})")
    return PlatformClient(base, token_provider)

def run_module():
    trace("==> Enter run_module()")
    args = dict(
        username=dict(type="str", required=True),
        email=dict(type="str", required=False),
        first_name=dict(type="str", required=False, default=""),
        last_name=dict(type="str", required=False, default=""),
        is_superuser=dict(type="bool", required=False, default=False),
        state=dict(type="str", required=False, default="present", choices=["present", "absent"]),

        # connection parameters
        base=dict(type="str", required=False),
        token=dict(type="str", required=False, no_log=True),
        verify=dict(type="raw", required=False),

        # NEW: agent address passed by action plugin
        agent_addr=dict(type="str", required=False),
    )

    module = AnsibleModule(argument_spec=args, supports_check_mode=True)

    # "Resolve desired state and build SDK client"
    username = module.params["username"]
    desired_state = module.params["state"]

    try:
        trace(f"username={username} desired_state={desired_state}")
        client = _client_from_params_or_env(module)
        repo = UsersRepo(client)
        trace("UsersRepo initialized")

        current = repo.get_by_name(username)

        # Absent path
        if desired_state == "absent":
        # --- Absent Path ---
            trace("state=absent path entered")
            if module.check_mode:
                trace("check_mode=True -> exiting early")
                module.exit_json(changed=bool(current), user=None)
            if current:
                trace(f"deleting existing user id={current.id}")
                repo.delete(current)
                module.exit_json(changed=True, user=None)
            trace("no user found; nothing to delete")
            module.exit_json(changed=False, user=None)

        # --- Present Path ---
        trace("state=present path entered")
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
            trace("user not found -> creating new user")
            if module.check_mode:
                trace("check_mode=True -> simulate create")
                module.exit_json(changed=True, user=desired.__dict__)
            created = repo.create(desired)
            trace(f"user created id={created.id}")
            module.exit_json(changed=True, user=created.__dict__)

        # Update path
        trace("user exists -> checking drift")
        changed = False
        if desired.email and desired.email != current.email:
            trace(f"email drift: current={current.email} desired={desired.email}")
            changed = True
            current.email = desired.email

        if (
            desired.first_name != current.first_name
            or desired.last_name != current.last_name
            or bool(desired.is_superuser) != bool(current.is_superuser)
        ):
            trace("name or superuser drift detected")
            changed = True
            current.first_name = desired.first_name
            current.last_name = desired.last_name
            current.is_superuser = bool(desired.is_superuser)

        if module.check_mode:
            module.exit_json(changed=changed, user=(current.__dict__ if current else desired.__dict__))

        if changed:
            trace("applying update to repo")
            updated = repo.update(current)
            trace(f"user updated id={updated.id}")
            module.exit_json(changed=True, user=updated.__dict__)
        else:
            trace("no changes detected -> exit clean")
            module.exit_json(changed=False, user=current.__dict__)

    except Exception as e:
        trace(f"EXCEPTION: {e}")
        module.fail_json(msg=str(e))
    finally:
        trace("<== Exit run_module()")

def main():
    run_module()


if __name__ == "__main__":
    main()

