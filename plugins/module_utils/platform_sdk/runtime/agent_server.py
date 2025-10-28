# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import sys
import json
import time
import threading
import socketserver
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import requests
from typing import Dict, Tuple, Optional

# ---- at top-level in agent_server.py ----
import time
from typing import Dict, Tuple, Optional, Any

class TTLNameIdCache:
    # key: (kind, scope, name) -> (id, expiry_epoch)
    def __init__(self, default_ttl: int = 300):
        self._d: Dict[Tuple[str, str, str], Tuple[str, float]] = {}
        self._ttl = default_ttl
        self._lock = threading.RLock()

    def _now(self) -> float:
        return time.time()

    def get(self, kind: str, scope: str, name: str) -> Optional[str]:
        k = (kind, scope, name)
        with self._lock:
            v = self._d.get(k)
            if not v:
                return None
            id_, exp = v
            if self._now() >= exp:
                self._d.pop(k, None)
                return None
            return id_

    def put(self, kind: str, scope: str, name: str, id_: str, ttl: Optional[int] = None):
        k = (kind, scope, name)
        with self._lock:
            self._d[k] = (id_, self._now() + float(ttl or self._ttl))

    def flush(self, kind: Optional[str] = None, scope: Optional[str] = None):
        with self._lock:
            if not kind and not scope:
                self._d.clear()
                return
            to_del = []
            for (k_kind, k_scope, _), _v in self._d.items():
                if (not kind or k_kind == kind) and (not scope or k_scope == scope):
                    to_del.append((k_kind, k_scope, _))
            for k in to_del:
                self._d.pop(k, None)

NAME_ID_CACHE = TTLNameIdCache(default_ttl=300)


class SessionPool:
    """
    Keep persistent requests.Session per (base_url) with shared TLS verify,
    and a single token provider guarded by a lock.
    - A single long-lived requests.Session → connection pooling + keep-alive.
    - The TLS verify setting (either True/False or a CA file path string).
    - The Bearer token with an expiry epoch.
    """
    def __init__(self):
        self._sessions: Dict[str, requests.Session] = {}
        self._verify_by_base: Dict[str, object] = {}  # bool | str (path)
        self._token_by_base: Dict[str, Tuple[str, float]] = {}  # token, expiry
        self._token_lock = threading.Lock()
        self._version_by_base: Dict[str, str] = {}
        self._lock = threading.RLock()
        
    def discover_version(self, base: str) -> str:
        sess = self.ensure_session(base)
        verify = self._verify_by_base.get(base, True)
        # Choose the ping that exists in your Gateway
        r = sess.get(f"{base.rstrip('/')}/api/", timeout=15, verify=verify)
        v = "unknown"
        if r.ok:
            try:
                j = r.json()
                # Adjust to whatever your gateway exposes
                v = j.get("version") or j.get("current_version") or "unknown"
            except Exception:
                pass
        self._version_by_base[base] = v
        return v

    def set_verify(self, base: str, verify: object):
        # Called by /bootstrap. Saves TLS and token info for the given base.
        with self._lock:
            self._verify_by_base[base] = verify

    def set_token(self, base: str, token: str, expiry: float):
        with self._lock:
            self._token_by_base[base] = (token, expiry)

    def ensure_session(self, base: str) -> requests.Session:
        """_summary_
         Returns the persistent Session for base, creating it once (lazy init).
         This is the heart of keep-alive: every task ends up reusing th 
        """
        with self._lock:
            sess = self._sessions.get(base)
            if not sess:
                sess = requests.Session()
                # small pool config can go here if needed
                self._sessions[base] = sess
            return sess

    def _ensure_token(self, base: str, token_provider_url: Optional[str]) -> str:
        """
        Token is set either by a one-time env bootstrap (action plugin) or via
        a call to /set_token. If token_provider_url is given, the agent can call
        out to fetch/refresh (left as an optional extension).
        """
        with self._token_lock:
            token, expiry = self._token_by_base.get(base, ("", 0.0))
            now = time.time()
            if token and now < (expiry - 30):
                return token
            # If you want active refresh, implement it here (call token_provider_url).
            # For now we just reuse current value; action plugin can set periodically.
            return token

    def request(self, base: str, method: str, path: str, params=None, json_body=None, headers=None):
        """_summary_
        Builds headers (Accept, User-Agent, optional Authorization).
        Computes URL as f"{base.rstrip('/')}{path}".
        Executes sess.request(..., verify=verify, timeout=30).
        Basic auth retry note: if 401/403 occurs, we don’t refresh yet—this is a known extension point.
        Parses response:
        If Content-Type starts with application/json, returns parsed JSON.
        Else returns .text (string) or None.
        Returns (status_code, content_type, body).

        Args:
            base (str): _description_
            method (str): _description_
            path (str): _description_
            params (_type_, optional): _description_. Defaults to None.
            json_body (_type_, optional): _description_. Defaults to None.
            headers (_type_, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        
        sess = self.ensure_session(base)
        verify = self._verify_by_base.get(base, True)
        token = self._ensure_token(base, token_provider_url=None)

        req_headers = {
            "Accept": "application/json",
            "User-Agent": "ansible.platform-agent/0.1",
        }
        if headers:
            req_headers.update(headers)
        if token:
            req_headers["Authorization"] = f"Bearer {token}"

        url = f"{base.rstrip('/')}{path}"
        r = sess.request(method=method, url=url, params=params, json=json_body, headers=req_headers, timeout=30, verify=verify)

        # Simple 401 retry once (if token got stale between ensure and request)
        if r.status_code in (401, 403) and token:
            # no active refresh implemented here; just surface the error
            pass

        ctype = r.headers.get("Content-Type", "")
        body = None
        if r.content:
            if ctype.startswith("application/json"):
                body = r.json()
            else:
                body = r.text
        return r.status_code, ctype, body


POOL = SessionPool()


class Handler(BaseHTTPRequestHandler):
    server_version = "AAPAgent/0.1"

    def _json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw or b"{}")

    def _send(self, code: int, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, {"ok": True})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/bootstrap":
            body = self._json()
            base = body["base"]
            verify = body.get("verify", True)
            token = body.get("token", "")
            expiry = float(body.get("expiry", time.time() + 3600))
            POOL.set_verify(base, verify)
            if token:
                POOL.set_token(base, token, expiry)
            return self._send(200, {"ok": True})

        if self.path == "/request":
            body = self._json()
            base = body["base"]
            method = body["method"]
            path = body["path"]
            params = body.get("params")
            json_body = body.get("json")
            headers = body.get("headers")
            try:
                status, ctype, data = POOL.request(base, method, path, params=params, json_body=json_body, headers=headers)
                return self._send(200, {"status": status, "ctype": ctype, "data": data})
            except Exception as e:
                return self._send(500, {"error": str(e)})
        if self.path == "/cache/get":
            body = self._json()
            kind  = body.get("kind","user")
            scope = body.get("scope","")   # e.g., org name or empty
            name  = body["name"]
            id_ = NAME_ID_CACHE.get(kind, scope, name)
            return self._send(200, {"id": id_})

        if self.path == "/cache/put":
            body = self._json()
            kind  = body.get("kind","user")
            scope = body.get("scope","")
            name  = body["name"]
            id_   = body["id"]
            ttl   = body.get("ttl")
            NAME_ID_CACHE.put(kind, scope, name, id_, ttl)
            return self._send(200, {"ok": True})

        if self.path == "/cache/flush":
            body = self._json()
            NAME_ID_CACHE.flush(kind=body.get("kind"), scope=body.get("scope"))
            return self._send(200, {"ok": True})
        
        if self.path == "/bootstrap":
            # ... existing code ...
            # discover and store
            v = POOL.discover_version(base)
            return self._send(200, {"ok": True, "version": v})

        return self._send(404, {"error": "not found"})


def run(addr: str = "127.0.0.1", port: int = 0):
    # port=0: OS picks a free port. We print it for the caller to capture.
    httpd = HTTPServer((addr, port), Handler)
    sa = httpd.socket.getsockname()
    print(json.dumps({"addr": sa[0], "port": sa[1]}), flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    # Allow: python agent_server.py [port]
    p = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    run("127.0.0.1", p)
