# -*- coding: utf-8 -*-
from __future__ import annotations

"""
PlatformClient
--------------
A small HTTP client used by ansible.platform modules via the internal SDK.

Modes:
  1) Direct (default): one requests.Session per task/process.
     - Token refresh guarded by a lock.
     - TLS verify from env AAP_VERIFY (true/false or CA path).

  2) Agent proxy (persistent): if AAP_AGENT_ADDR is set, proxy requests to a
     local agent which maintains a long-lived Session, shared token, and caches.
     - Great for multi-task, multi-process plays (perf & stability).
     - See runtime/agent_server.py and aap_agent action plugin.

Environment:
  AAP_BASE   : Base URL (e.g., https://aap.example.com)
  AAP_TOKEN  : Bearer token (if not using a token bus/provider)
  AAP_VERIFY : "", "true"/"false"/"1"/"0"/"yes"/"no", or a CA file path
  AAP_AGENT_ADDR : "127.0.0.1:PORT" for agent mode (optional)

Authoritative token source is provided by `token_provider()`; by default we
wrap AAP_TOKEN with a fixed (1h) expiry. Swap with a runtime state-bus as needed.
"""

import os
import time
import json
import threading
from typing import Optional, Any, Callable
from .api import api_factory

import requests
from .abc import TokenProvider

try:
    # stdlib only for agent calls
    import urllib.request as _urlreq
    import urllib.error as _urlerr
except Exception:  # pragma: no cover
    _urlreq = None
    _urlerr = None


class PlatformClient:
    """
    Shared HTTP client with optional agent proxy.

    - token_provider() -> (token: str, expiry_epoch: float)
    - TLS verify via env AAP_VERIFY:
        ""/"true"/unset -> verify=True (system CA)
        "false"         -> verify=False (demo/self-signed)
        "/path/ca.pem"  -> verify="/path/ca.pem"
    PlatformClient gives modules a single API: request(method, path, **kw).
    Under the hood it can run in either mode:

    Agent mode (persistent) — if AAP_AGENT_ADDR is set:
    No local requests.Session.
    Proxies calls to the agent via POST http://<addr>/request.
    The agent keeps a long-lived requests.Session, TLS verify settings, and token state → TCP keep-alive & shared state across tasks/forks.
    Direct mode (per-process) — default if no AAP_AGENT_ADDR:
    Creates one requests.Session() in the current module process.
    Uses local locks for token refresh and per-call concurrency.
    No persistence across tasks, just within the current process. 
    
    """
    

    def __init__(self, base_url: str, token_provider: TokenProvider, agent_addr: Optional[str] = None):
        # base_url: AAP Gateway base; normalized (no trailing slash).
        # token_provider: the function that returns (token, expiry) when needed.
        
        self._base = base_url.rstrip("/")
        self._token_provider = token_provider

        # Locks for direct mode
        self._lock = threading.RLock()
        self._token_lock = threading.Lock()
        self._token: Optional[str] = None
        self._expiry: float = 0.0
        self._version: Optional[str] = None

        # TLS verify setting
        v = (os.environ.get("AAP_VERIFY") or "").strip().lower()
        if v in ("", "true", "1", "yes"):
            self._verify = True
        elif v in ("false", "0", "no"):
            self._verify = False
        else:
            # treat non-boolean value as a CA file path
            self._verify = os.environ.get("AAP_VERIFY")

        # Agent proxy (persistent) vs direct mode
        self._agent_addr = agent_addr or os.environ.get("AAP_AGENT_ADDR")
        if self._agent_addr:
            # Agent mode: no local Session; agent owns persistence & locks
            self._session = None
        else:
            # Direct mode: one Session per task/process
            self._session = requests.Session()

    # -------------------------
    # Construction helpers
    # -------------------------
    @classmethod
    def from_env(cls) -> "PlatformClient":
        """
        Convenience: read AAP_BASE, AAP_TOKEN and optional AAP_AGENT_ADDR from env.
        """
        base = os.environ.get("AAP_BASE") or os.environ.get("AapBase")
        token = os.environ.get("AAP_TOKEN")
        if not base or not token:
            raise RuntimeError("AAP_BASE and AAP_TOKEN must be set in environment (or use a runtime binding).")

        def provider() -> tuple[str, float]:
            # Simple fixed-expiry (1h). Replace with state-bus backed provider as needed.
            return token, time.time() + 3600

        return cls(base, provider, agent_addr=os.environ.get("AAP_AGENT_ADDR"))

    def api(self):
        return api_factory(self.get_version() or os.environ.get("AAP_VERSION"))
    # -------------------------
    # Token handling (direct mode)
    # -------------------------
    def _ensure_token(self) -> None:
        """
        Ensure we have a fresh token in direct mode.
        Agent mode delegates token/locks to the agent.
        """
        if self._agent_addr:
            return  # agent owns tokens

        now = time.time()
        if self._token and now < (self._expiry - 30):
            return

        with self._token_lock:
            now = time.time()
            if self._token and now < (self._expiry - 30):
                return
            self._token, self._expiry = self._token_provider()
            
    # Add tiny helpers to call the agent cache (only active in agent mode)       
    def cache_get(self, kind: str, name: str, scope: str = "") -> Optional[str]:
        if not self._agent_addr:
            return None
        res = self._agent_call({"kind": kind, "name": name, "scope": scope}, path="/cache/get")
        return res.get("id")

    def cache_put(self, kind: str, name: str, id_: str, scope: str = "", ttl: Optional[int] = None) -> None:
        if not self._agent_addr:
            return
        payload = {"kind": kind, "name": name, "id": id_, "scope": scope}
        if ttl is not None:
            payload["ttl"] = int(ttl)
        self._agent_call(payload, path="/cache/put")
     
    # Client: expose the version (agent or direct discovery)
    # If agent returns version, keep it; otherwise discover lazily in direct mode:    
        
    def set_version(self, v: str):
        self._version = v

    def get_version(self) -> Optional[str]:
        if self._version:
            return self._version
        if self._agent_addr:
            # optional: add /version endpoint; or return from bootstrap and set it in action plugin
            return self._version
        # direct mode discovery (once)
        try:
            self._ensure_token()
            r = self._session.get(f"{self._base}/api/", timeout=15, verify=self._verify)
            if r.ok:
                j = r.json()
                self._version = j.get("version") or j.get("current_version")
        except Exception:
            pass
        return self._version

    # -------------------------
    # Agent proxy
    # -------------------------
    def _agent_call(self, payload: dict, path: str = "/request") -> dict:
        """
        Call the local agent (HTTP) with a small JSON payload.

        Expected response:
          { "status": 200, "ctype": "application/json", "data": <json or text> }
        """
        if not _urlreq:
            raise RuntimeError("urllib not available for agent calls")

        req = _urlreq.Request(
            url=f"http://{self._agent_addr}{path}",
            # url=f"http://{self._agent_addr}/request",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with _urlreq.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except Exception as e:  # pragma: no cover
            raise requests.RequestException(f"Agent request failed: {e}") from e

    # -------------------------
    # Public request API
    # -------------------------
    def request(self, method: str, path: str, **kw) -> Any:
        """
        Perform an HTTP request to AAP. If agent is configured, proxy to agent.
        """
        if self._agent_addr:
            # Persistent agent path
            payload = {
                "base": self._base,
                "method": method,
                "path": path,
            }
            if "params" in kw and kw["params"] is not None:
                payload["params"] = kw["params"]
            if "json" in kw and kw["json"] is not None:
                payload["json"] = kw["json"]

            res = self._agent_call(payload)
            status = int(res.get("status", 500))
            if status >= 400:
                # Normalize to requests-like error for callers
                raise requests.HTTPError(f"Agent proxy error: status={status}, body={res.get('data')}")
            return res.get("data")

        # Direct mode (current behavior)
        self._ensure_token()
        with self._lock:
            self._session.headers.update({
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "ansible.platform-sdk/0.1",
                "Accept": "application/json",
            })
            kw.setdefault("timeout", 30)
            kw.setdefault("verify", self._verify)
            url = f"{self._base}{path}"

            r = self._session.request(method, url, **kw)
            if r.status_code in (401, 403):
                # refresh once
                self._token, self._expiry = self._token_provider()
                self._session.headers.update({"Authorization": f"Bearer {self._token}"})
                r = self._session.request(method, url, **kw)

            r.raise_for_status()
            ctype = r.headers.get("Content-Type", "")
            if r.content and ctype.startswith("application/json"):
                return r.json()
            return r.text if r.content else None
