import os
import time
import json
import threading
from typing import Optional, Any, Callable

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
    """

    def __init__(self, base_url: str, token_provider: TokenProvider, agent_addr: Optional[str] = None):
        self._base = base_url.rstrip("/")
        self._token_provider = token_provider

        # Locks for direct mode
        self._lock = threading.RLock()
        self._token_lock = threading.Lock()
        self._token: Optional[str] = None
        self._expiry: float = 0.0

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

    # -------------------------
    # Agent proxy
    # -------------------------
    def _agent_call(self, payload: dict) -> dict:
        """
        Call the local agent (HTTP) with a small JSON payload.

        Expected response:
          { "status": 200, "ctype": "application/json", "data": <json or text> }
        """
        if not _urlreq:
            raise RuntimeError("urllib not available for agent calls")

        req = _urlreq.Request(
            url=f"http://{self._agent_addr}/request",
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