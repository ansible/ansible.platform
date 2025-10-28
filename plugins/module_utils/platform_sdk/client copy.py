from __future__ import annotations

import os
import time
import threading
from typing import Optional, Any, Callable

import requests
from .abc import TokenProvider


"""
Each task runs the module in a new Python process.
Your PlatformClient builds a requests.Session() per task, so HTTP keep-alive doesn’t persist across tasks/forks.
You do have a clean SDK and typed repos, which is the foundation.
"""
class PlatformClient:
    """
    Shared HTTP client with token refresh guarded by locks.
    - token_provider() -> (token: str, expiry_epoch: float)
    - TLS verify via env AAP_VERIFY:
        ""/"true"/unset -> verify=True (system CA)
        "false"         -> verify=False (demo-only)
        "/path/ca.pem"  -> verify="/path/ca.pem"
    """
    def __init__(self, base_url: str, token_provider: TokenProvider):
        self._base = base_url.rstrip("/")
        self._session = requests.Session()
        self._lock = threading.RLock()        # coarse lock around requests.Session
        self._token_lock = threading.Lock()   # serialize refresh
        self._token_provider = token_provider
        self._token: Optional[str] = None
        self._expiry: float = 0.0

        v = os.environ.get("AAP_VERIFY", "").strip().lower()
        if v in ("", "true", "1", "yes"):
            self._verify = True
        elif v in ("false", "0", "no"):
            self._verify = False
        else:
            self._verify = os.environ.get("AAP_VERIFY")  # file path

    @classmethod
    def from_env(cls) -> "PlatformClient":
        """Convenience for action plugins: read base and token from env."""
        base = os.environ.get("AAP_BASE") or os.environ.get("AapBase")  # add variants if needed
        token = os.environ.get("AAP_TOKEN")
        if not base or not token:
            raise RuntimeError("AAP_BASE and AAP_TOKEN must be set in environment or use runtime bindings.")
        def provider() -> tuple[str, float]:
            return token, time.time() + 3600
        return cls(base, provider)

    def _ensure_token(self) -> None:
        now = time.time()
        if self._token and now < (self._expiry - 30):
            return
        with self._token_lock:
            now = time.time()
            if self._token and now < (self._expiry - 30):
                return
            self._token, self._expiry = self._token_provider()

    def request(self, method: str, path: str, **kw) -> Any:
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
