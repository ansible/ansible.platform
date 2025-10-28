# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
import json
import threading
from typing import Optional, Any, Dict, Tuple

import requests
from abc import TokenProvider

# Optional stdlib HTTP for agent calls (no external deps)
try:
    import urllib.request as _urlreq
except Exception:  # pragma: no cover
    _urlreq = None


class PlatformClient:
    """
    Unified Platform client with two execution modes:

    1) Agent mode (preferred): if AAP_AGENT_ADDR is set (or passed), all HTTP
       is proxied to a long-lived local agent process that owns persistent
       requests.Session(), TLS verify, tokens, and caches.
       - Benefits: connection reuse across tasks/forks, centralized locks/caches.

    2) Direct mode: per-process requests.Session() with local token refresh and locks.

    TLS verification via env AAP_VERIFY:
      ""/"true"/unset -> True (use system CA)
      "false"         -> False (demo/self-signed)
      "/path/ca.pem"  -> str path to a CA bundle
    """

    # --------------------------------------------------------------------- #
    # Construction
    # --------------------------------------------------------------------- #
    def __init__(
        self,
        base_url: str,
        token_provider: TokenProvider,
        agent_addr: Optional[str] = None,
    ):
        self._base = base_url.rstrip("/")
        self._token_provider = token_provider

        # direct-mode locks / token cache
        self._lock = threading.RLock()
        self._token_lock = threading.Lock()
        self._token: Optional[str] = None
        self._expiry: float = 0.0

        # TLS verify
        v = (os.environ.get("AAP_VERIFY") or "").strip().lower()
        if v in ("", "true", "1", "yes"):
            self._verify: bool | str = True
        elif v in ("false", "0", "no"):
            self._verify = False
        else:
            # treat as file path (leave original case)
            self._verify = os.environ.get("AAP_VERIFY") or True

        # Agent vs Direct
        self._agent_addr = agent_addr or os.environ.get("AAP_AGENT_ADDR")
        self._session: Optional[requests.Session] = None if self._agent_addr else requests.Session()

        # Platform version (e.g. "2.7.x", "2.8.x")
        self._version: Optional[str] = os.environ.get("AAP_VERSION") or None

    @classmethod
    def from_env(cls) -> "PlatformClient":
        """
        Convenience constructor reading:
          - AAP_BASE, AAP_TOKEN, optional AAP_AGENT_ADDR, AAP_VERSION
        """
        base = os.environ.get("AAP_BASE") or os.environ.get("AapBase")
        token = os.environ.get("AAP_TOKEN")
        if not base or not token:
            raise RuntimeError("AAP_BASE and AAP_TOKEN must be set in environment (or supply via runtime bindings).")

        def provider() -> Tuple[str, float]:
            # Simple fixed expiry; swap with state-bus or OAuth refresh as needed
            return token, time.time() + 3600

        client = cls(base, provider, agent_addr=os.environ.get("AAP_AGENT_ADDR"))
        # Seed version from env if provided (action plugin may set it post-bootstrap)
        v = os.environ.get("AAP_VERSION")
        if v:
            client.set_version(v)
        return client

    # --------------------------------------------------------------------- #
    # Version handling & API façade
    # --------------------------------------------------------------------- #
    def set_version(self, version: str) -> None:
        """Explicitly set platform version (e.g., provided by action plugin after /bootstrap)."""
        self._version = version

    def get_version(self) -> Optional[str]:
        """
        Return cached/detected platform version.
        - In agent mode: action plugin should set AAP_VERSION (from /bootstrap response),
          otherwise we leave as-is (you can add an agent /version endpoint later).
        - In direct mode: attempt a lazy discovery once (best-effort).
        """
        if self._version:
            return self._version

        if self._agent_addr:
            # No agent endpoint defined here; rely on action plugin to set AAP_VERSION.
            return None

        # Direct mode: try discovery once
        try:
            self._ensure_token()
            url_candidates = [f"{self._base}/api/", f"{self._base}/api/v2/ping/"]
            for url in url_candidates:
                r = self._session.get(url, timeout=15, verify=self._verify)  # type: ignore[arg-type]
                if r.ok:
                    try:
                        j = r.json()
                        ver = j.get("version") or j.get("current_version")
                        if ver:
                            self._version = str(ver)
                            break
                    except Exception:
                        pass
        except Exception:
            pass
        return self._version

    def api(self):
        """
        Return a version-aware API façade implementation (BaseAPI subclass).
        Repositories should call paths/normalizers via this façade rather than
        hard-coding URLs/fields.
        """
        # Local import to avoid circulars for consumers that don't need it
        from .api import api_factory
        return api_factory(self.get_version() or os.environ.get("AAP_VERSION"))

    # --------------------------------------------------------------------- #
    # Direct-mode token refresh
    # --------------------------------------------------------------------- #
    def _ensure_token(self) -> None:
        if self._agent_addr:
            return  # tokens owned by agent in agent mode
        now = time.time()
        if self._token and now < (self._expiry - 30):
            return
        with self._token_lock:
            now = time.time()
            if self._token and now < (self._expiry - 30):
                return
            self._token, self._expiry = self._token_provider()

    # --------------------------------------------------------------------- #
    # Agent helpers (proxy + cache)
    # --------------------------------------------------------------------- #
    def _agent_call(self, payload: Dict[str, Any], path: str = "/request") -> Dict[str, Any]:
        if not self._agent_addr or not _urlreq:
            raise RuntimeError("Agent calls require AAP_AGENT_ADDR and stdlib urllib.request")
        req = _urlreq.Request(
            url=f"http://{self._agent_addr}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _urlreq.urlopen(req, timeout=30) as resp:  # type: ignore[attr-defined]
            raw = resp.read()
            return json.loads(raw) if raw else {}

    # Simple name→id cache helpers (agent mode only; no-ops in direct mode)
    def cache_get(self, kind: str, name: str, scope: str = "") -> Optional[str]:
        if not self._agent_addr:
            return None
        res = self._agent_call({"kind": kind, "name": name, "scope": scope}, path="/cache/get")
        return res.get("id")

    def cache_put(self, kind: str, name: str, id_: str, scope: str = "", ttl: Optional[int] = None) -> None:
        if not self._agent_addr:
            return
        payload: Dict[str, Any] = {"kind": kind, "name": name, "id": id_, "scope": scope}
        if ttl is not None:
            payload["ttl"] = int(ttl)
        self._agent_call(payload, path="/cache/put")

    # --------------------------------------------------------------------- #
    # Public request API
    # --------------------------------------------------------------------- #
    def request(self, method: str, path: str, **kw) -> Any:
        """
        Perform an HTTP request against the Platform.

        Agent mode:
          - Proxy to /request with {base, method, path, params, json}
          - Returns unwrapped JSON/text like direct mode (errors raised on 4xx/5xx)

        Direct mode:
          - Uses a local requests.Session with token refresh and verify handling
        """
        if self._agent_addr:
            payload: Dict[str, Any] = {"base": self._base, "method": method, "path": path}
            if "params" in kw and kw["params"] is not None:
                payload["params"] = kw["params"]
            if "json" in kw and kw["json"] is not None:
                payload["json"] = kw["json"]

            res = self._agent_call(payload, path="/request")
            status = int(res.get("status", 500))
            if status >= 400:
                # Normalize to requests-like error
                raise requests.HTTPError(f"Agent proxy error: status={status}, body={res.get('data')}")
            return res.get("data")

        # Direct mode
        self._ensure_token()
        with self._lock:
            assert self._session is not None  # for type-checkers
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
                # one refresh attempt
                self._token, self._expiry = self._token_provider()
                self._session.headers.update({"Authorization": f"Bearer {self._token}"})
                r = self._session.request(method, url, **kw)

            r.raise_for_status()
            ctype = r.headers.get("Content-Type", "")
            if r.content and isinstance(ctype, str) and ctype.startswith("application/json"):
                return r.json()
            return r.text if r.content else None
