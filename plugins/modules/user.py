# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.ansible.platform.plugins.module_utils.platform_sdk import PlatformClient, UsersRepo, User

import os, time, sys, datetime

DEBUG_TRACE = os.environ.get("AAP_AGENT_TRACE", "0") == "1"
def trace(msg: str):
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

DOCUMENTATION = r"""
module: user
short_description: Manage Ansible Automation Platform users (manager-only transport)
description:
  - Ensure a user is present or absent in AAP using the internal Platform SDK layer.
  - This build is manager-only: the module must receive a BaseManager agent address and authkey.
options:
  username:
    type: str
    required: true
  email:
    type: str
  first_name:
    type: str
  last_name:
    type: str
  is_superuser:
    type: bool
    default: false
  state:
    type: str
    choices: [present, absent]
    default: present
  base:
    type: str
    required: true
  token:
    type: str
    no_log: true
  verify:
    type: raw
  agent_addr:
    type: str
    required: true
  agent_authkey:
    type: str
    required: true
    no_log: true
"""

def _client_from_params_or_env(module: AnsibleModule) -> PlatformClient:
    base = module.params.get("base") or os.environ.get("AAP_BASE")
    token_value = module.params.get("token") or os.environ.get("AAP_TOKEN")
    verify = module.params.get("verify")
    if verify is None:
        verify = os.environ.get("AAP_VERIFY", "")

    agent_addr = module.params.get("agent_addr") or os.environ.get("AAP_AGENT_ADDR")
    agent_authkey = module.params.get("agent_authkey") or os.environ.get("AAP_AGENT_AUTHKEY")

    if not base:
        module.fail_json(msg="Missing AAP base: provide 'base' or set AAP_BASE.")
    if not agent_addr or not agent_authkey:
        module.fail_json(msg="Manager-only build: missing agent_addr/agent_authkey. Action plugin must pass these.")

    # normalize verify to env (agent uses it during bootstrap; harmless here)
    os.environ["AAP_VERIFY"] = ("true" if verify else "false") if isinstance(verify, bool) else str(verify)

    # token is OPTIONAL now; if missing, client won’t add an Authorization header
    if token_value:
        def token_provider():
            import time
            return token_value, time.time() + 3600
    else:
        token_provider = None

    trace(f"creating PlatformClient(manager-only, base={base}, agent={agent_addr}, token={'yes' if token_value else 'no'})")
    return PlatformClient(base, token_provider, agent_addr=agent_addr, agent_authkey=agent_authkey)

def run_module():
    args = dict(
        username=dict(type="str", required=True),
        email=dict(type="str", required=False),
        first_name=dict(type="str", required=False, default=""),
        last_name=dict(type="str", required=False, default=""),
        is_superuser=dict(type="bool", required=False, default=False),
        state=dict(type="str", required=False, default="present", choices=["present", "absent"]),

        # connection parameters
        base=dict(type="str", required=True),
        token=dict(type="str", required=False, no_log=True),      # <-- NOT required
        verify=dict(type="raw", required=False),

        # Manager agent details
        agent_addr=dict(type="str", required=True),
        agent_authkey=dict(type="str", required=True, no_log=True),
    )

    module = AnsibleModule(argument_spec=args, supports_check_mode=True)

    username = module.params["username"]
    desired_state = module.params["state"]

    try:
        trace(f"username={username} desired_state={desired_state}")
        client = _client_from_params_or_env(module)
        repo = UsersRepo(client)
        trace("UsersRepo initialized")

        current = repo.get_by_name(username)

        if desired_state == "absent":
            trace("state=absent path entered")
            if module.check_mode:
                module.exit_json(changed=bool(current), user=None)
            if current:
                repo.delete(current)
                module.exit_json(changed=True, user=None)
            module.exit_json(changed=False, user=None)

        trace("state=present path entered")
        desired = User(
            id=current.id if current else None,
            username=username,
            email=module.params.get("email"),
            first_name=module.params.get("first_name") or "",
            last_name=module.params.get("last_name") or "",
            is_superuser=bool(module.params.get("is_superuser")),
        )

        if not current:
            if module.check_mode:
                module.exit_json(changed=True, user=desired.__dict__)
            created = repo.create(desired)
            module.exit_json(changed=True, user=created.__dict__)

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
        trace(f"EXCEPTION: {e}")
        module.fail_json(msg=str(e))
    finally:
        trace("<== Exit run_module()")

def main():
    run_module()

if __name__ == "__main__":
    main()
