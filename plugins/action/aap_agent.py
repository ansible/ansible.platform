# plugins/action/aap_agent.py
from __future__ import annotations
from ansible.plugins.action import ActionBase
import os, sys, json, time, subprocess, urllib.request

ADDRFILE = "/tmp/aap_agent.addr"   # JSON: {"addr":"127.0.0.1","port":12345}

def _alive(addr: str) -> bool:
    try:
        with urllib.request.urlopen(f"http://{addr}/healthz", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False

def _bootstrap(addr: str, base: str, token: str, verify):
    """_summary_
    This helper function sends an HTTP POST request to your running agent process:
    Each Ansible task runs in a separate Python process.
    Without a bootstrap step, each module would need to re-read AAP_BASE and AAP_TOKEN, rebuild a session, and reconnect to AAP every time.
    By bootstrapping once, the agent:
    holds persistent requests.Session objects,
    reuses sockets (keep-alive),
    shares token state across all forks/tasks.
    So “bootstrap” is really the state injection step — teaching the agent who to talk to and with what credentials before any module starts using it.
    """
    payload = {"base": base, "token": token, "expiry": time.time() + 3600, "verify": verify}
    req = urllib.request.Request(
        url=f"http://{addr}/bootstrap",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        if resp.status != 200:
            raise RuntimeError(f"bootstrap failed: {resp.status}")

class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        result = {"changed": False}

        # Gather connection params from env or task args
        # We collect connection details (prefer env; fall back to args).
        base = os.environ.get("AAP_BASE") or self._task.args.get("base")
        token = os.environ.get("AAP_TOKEN") or self._task.args.get("token")
        verify = os.environ.get("AAP_VERIFY", self._task.args.get("verify", ""))

        if not base or not token:
            result.update(failed=True, msg="AAP_BASE and AAP_TOKEN must be set (env or args) to bootstrap agent")
            return result

        # Compute python and agent path WITHOUT using expand_user_and_vars
        # launch the agent using the same interpreter Ansible is using to run your playbook.
        # task_vars['ansible_playbook_python'] is set by Ansible and points to the interpreter running ansible-playbook. This matters if you’re in a virtualenv/venv or custom Python—so the agent sees the same site-packages, SSL config, certs, etc.
        # If for some reason that var isn’t present, we fall back to sys.executable (the interpreter running the action plugin itself). Either way, you avoid hardcoding python/python3.
        
        py = (task_vars or {}).get("ansible_playbook_python") or sys.executable
        
        # get a stable, absolute directory for the current action plugin file (aap_agent.py).
        # __file__ is the path to aap_agent.py; abspath() resolves it to an absolute path; dirname() strips the filename to leave just the directory.
        
        here = os.path.dirname(os.path.abspath(__file__))
        agent_path = os.path.normpath(os.path.join(here, "..", "module_utils", "platform_sdk", "runtime", "agent_server.py"))

        # Try reuse existing agent if present
        # If the agent is already up, we reuse it (idempotent behavior).
        addr = None
        
        # What: Looks for /tmp/aap_agent.addr (a tiny JSON file you wrote the first time the agent started).
        # Why: If it exists and parses, we get the last-known address:port of the already-running agent—so we don’t start another one.
        # Resilience: If the file is corrupt/unreadable, we fall back to addr=None and treat it like “no agent”.
        
        if os.path.exists(ADDRFILE):
            try:
                with open(ADDRFILE, "r") as f:
                    info = json.load(f)
                addr = f"{info['addr']}:{info['port']}"
            except Exception:
                addr = None

        # Start agent if not alive
        if not addr or not _alive(addr):
            # Launch agent; it prints a JSON line with addr/port on startup
            # We launch a small HTTP server in a separate process (the agent).
            # The agent prints its {addr, port} once, we capture and persist it.
            # This is your long-lived process that will hold persistent requests.Session objects.
            
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            proc = subprocess.Popen(
                [py, agent_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            first = proc.stdout.readline().strip()
            if not first:
                err = proc.stderr.read()
                result.update(failed=True, msg=f"Failed to start agent: {err or 'no output'}")
                return result
            try:
                info = json.loads(first)
            except json.JSONDecodeError as e:
                err = proc.stderr.read()
                result.update(failed=True, msg=f"Invalid agent banner: {first}; stderr={err}")
                return result

            addr = f"{info['addr']}:{info['port']}"
            with open(ADDRFILE, "w") as f:
                json.dump(info, f)
            result["changed"] = True

        # Bootstrap connection params into agent and return the address
        # giving the background agent process all the connection details it needs (base URL, token, TLS verify) so that it can start making API calls on behalf of future module tasks.
        resp = _bootstrap(addr, base, token, verify)
        version = resp.get("version")
        if version:
            os.environ["AAP_VERSION"] = version
        result["aap_agent_addr"] = addr
        result["msg"] = "AAP agent ready"
        return result
