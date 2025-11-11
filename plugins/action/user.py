# plugins/action/user.py
from __future__ import annotations
from ansible.plugins.action import ActionBase
import os, sys, datetime
from ._ensure_agent import ensure_agent

DEBUG_TRACE = os.environ.get("AAP_AGENT_TRACE", "0") == "1"
def trace(msg: str):
    if not DEBUG_TRACE: return
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[TRACE {ts}] user.py: {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        with open("/tmp/aap_agent_debug.log", "a") as f: f.write(line + "\n")
    except Exception: pass

class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        trace("==> Enter ActionModule.run()")
        result = {"changed": False}

        args = dict(self._task.args or {})
        base   = args.get("base")   or os.environ.get("AAP_BASE")
        token  = args.get("token")  or os.environ.get("AAP_TOKEN")
        verify = args.get("verify") if "verify" in args else os.environ.get("AAP_VERIFY", "")

        if not base or not token:
            return {"failed": True, "changed": False, "msg": "Missing base/token (pass params or set AAP_BASE/AAP_TOKEN)"}

        py = (task_vars or {}).get("ansible_playbook_python") or sys.executable
        here = os.path.dirname(os.path.abspath(__file__))
        agent_path = os.path.normpath(os.path.join(
            here, "..", "module_utils", "platform_sdk", "runtime", "agent_server_mp.py"
        ))
        trace(f"Interpreter={py} ; agent_path={agent_path}")

        # ensure (and reuse) the same agent across tasks
        addr = ensure_agent(py, agent_path, base.rstrip("/"), token, verify)
        trace(f"Agent ready at {addr}")
        os.environ["AAP_AGENT_ADDR"] = addr  # helps downstream client in direct env read

        # pass agent_addr to the module explicitly
        args.pop("token", None)  # avoid re-sending secrets
        args["agent_addr"] = addr

        # build a redacted copy for logging (never log secrets)
        safe_args = {}
        for key, val in args.items():
            if key in ("token", "password", "api_key", "secret"):
                safe_args[key] = "***"
            else:
                safe_args[key] = val

        trace(f"Invoking module ansible.platform.user with args={safe_args}")

        res = self._execute_module(
            module_name="ansible.platform.user",
            module_args=args,
            task_vars=task_vars,
            wrap_async=False,
            tmp=tmp,
        )
        result.update(res)
        trace("<== Exit ActionModule.run()")
        return result
