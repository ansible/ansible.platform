# plugins/module_utils/platform_sdk/client.py
from __future__ import annotations
import os, sys, datetime
from typing import Optional, Dict, Any
import urllib.parse

DEBUG_TRACE = os.environ.get("AAP_AGENT_TRACE", "0") == "1"

def trace(msg: str):
    if not DEBUG_TRACE:
        return
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[TRACE {ts}] client.py: {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        with open("/tmp/aap_agent_debug.log", "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

class _ManagerAgentTransport:
    def __init__(self, agent_addr: str, authkey_hex: str):
        from multiprocessing.managers import BaseManager
        # --- NEW: normalize inputs ---
        if not agent_addr or not authkey_hex:
            raise ValueError("agent_addr and agent_authkey are required for manager transport")
        agent_addr = agent_addr.strip()
        authkey_hex = authkey_hex.strip()                 # <— important
        if ":" not in agent_addr:
            raise ValueError("agent_addr must be 'host:port'")
        host, port_s = agent_addr.split(":", 1)
        self._address = (host, int(port_s))
        self._authkey = bytes.fromhex(authkey_hex)

        class AgentManager(BaseManager): ...
        AgentManager.register("Agent")
        try:
            self._mgr = AgentManager(address=self._address, authkey=self._authkey)
            self._mgr.connect()
        except Exception as e:
            # --- NEW: friendlier diagnostics ---
            raise RuntimeError(f"Failed to connect to agent at {host}:{port_s} "
                               f"(authkey_len={len(authkey_hex)}): {e!r}") from e
        self._agent = self._mgr.Agent()

    def request(self, base: str, method: str, path: str, params=None, json_body=None, headers=None) -> Dict[str, Any]:
        return self._agent.request(base, method, path, params=params, json_body=json_body, headers=headers)

    def bulk(self, base: str, jobs: list[dict]) -> Dict[str, Any]:
        return self._agent.bulk(base, jobs)

class PlatformClient:
    """
    Manager-only client that always proxies to the BaseManager agent.
    token_provider may be None (then no Authorization header is sent; agent's stored token is used).
    """
    def __init__(self, base: str, token_provider, agent_addr: str, agent_authkey: str):
        if not agent_addr or not agent_authkey:
            raise ValueError("Manager-only client requires agent_addr and agent_authkey")
        self.base = (base or "").rstrip("/")
        self.token_provider = token_provider            # <-- may be None now
        self.agent_addr = agent_addr
        self.agent_authkey = agent_authkey
        self._agent_transport = _ManagerAgentTransport(self.agent_addr, self.agent_authkey)
        trace(f"init base={self.base} agent=manager[{self.agent_addr}] token={'yes' if token_provider else 'no'}")

    def _auth_header(self) -> Dict[str, str]:
        # If no provider, rely on the Agent's stored token
        if not self.token_provider:
            return {}
        token, _ = self.token_provider()
        return {"Authorization": f"Bearer {token}"} if token else {}

    def request(self, method: str, path: str, params=None, json_body=None, headers=None) -> Any:
        headers = dict(headers or {})
        headers.setdefault("Accept", "application/json")
        headers.setdefault("User-Agent", "ansible.platform-sdk/manager-only/0.1")
        path = path if path.startswith("/") else "/" + path

        qp = f"?{urllib.parse.urlencode(params, doseq=True)}" if params else ""
        trace(f"via manager → {method} {self.base}{path}{qp}")

        env = self._agent_transport.request(
            base=self.base,
            method=method,
            path=path,
            params=params,
            json_body=json_body,
            headers=headers | self._auth_header(),   # may be empty
        )
        status = int(env.get("status", 500))
        if status >= 400 or not env.get("ok", False):
            raise RuntimeError(f"Agent request failed: {status}: {env.get('error')}")
        return env.get("data")
