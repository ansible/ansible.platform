# plugins/module_utils/platform_sdk/client.py
from __future__ import annotations
import os, sys, time, datetime
from typing import Optional, Dict, Any
import urllib.request
import urllib.parse
import requests
import json as _json  # protect against shadowing

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

def _resolve_verify(v: str | bool) -> bool | str:
    if isinstance(v, bool):
        return v
    s = (v or "").strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return v or True

class PlatformClient:
    """
    Minimal client that can call AAP either directly (requests) or via the local agent
    (HTTP POST /request to AAP agent). Decision is based on agent_addr param or AAP_AGENT_ADDR env.
    """
    def __init__(self, base: str, token_provider, agent_addr: Optional[str] = None):
        self.base = (base or "").rstrip("/")
        self.token_provider = token_provider
        self.agent_addr = agent_addr or os.environ.get("AAP_AGENT_ADDR")
        # verify is only used for DIRECT mode; agent handles verify internally from /bootstrap
        self.verify = _resolve_verify(os.environ.get("AAP_VERIFY", "true"))
        self._sess = requests.Session()
        trace(f"init base={self.base} agent_addr={self.agent_addr or 'direct'} verify={self.verify}")

    def _auth_header(self) -> Dict[str, str]:
        token, _ = self.token_provider()
        return {"Authorization": f"Bearer {token}"} if token else {}

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        If agent_addr is set → proxy via agent (/request).
        Else → direct HTTPS to base+path.
        Returns parsed JSON (dict/obj) or raises on non-2xx.
        """
        headers = dict(headers or {})
        headers.setdefault("Accept", "application/json")
        headers.setdefault("User-Agent", "ansible.platform-sdk/0.1")

        # Normalize path
        path = path if path.startswith("/") else "/" + path

        if self.agent_addr:
            # -------- via agent --------
            url = f"http://{self.agent_addr}/request"
            payload = {
                "base": self.base,
                "method": method,
                "path": path,
                "params": params,
                "json": json_body,  # agent expects key 'json'
                "headers": headers | self._auth_header(),
            }
            data = _json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url=url, data=data, headers={"Content-Type": "application/json"}, method="POST"
            )
            qp = f"?{urllib.parse.urlencode(params, doseq=True)}" if params else ""
            trace(f"via agent → {method} {self.base}{path}{qp}")
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read() or b"{}"
                if resp.status != 200:
                    raise RuntimeError(f"Agent request failed: HTTP {resp.status}")
                env = _json.loads(raw.decode("utf-8"))
                status = int(env.get("status", 500))
                if status >= 400:
                    raise RuntimeError(f"Agent request failed: {status}: {env.get('error')}")
                return env.get("data")

        # -------- direct mode --------
        url = f"{self.base}{path}"
        if params:
            q = urllib.parse.urlencode(params, doseq=True)
            trace(f"direct → {method} {url}?{q}")
        else:
            trace(f"direct → {method} {url}")

        r = self._sess.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
            headers=headers | self._auth_header(),
            timeout=30,
            verify=self.verify,
        )
        ctype = r.headers.get("Content-Type", "")
        if r.status_code >= 400:
            try:
                body = r.json() if isinstance(ctype, str) and ctype.startswith("application/json") else r.text
            except Exception:
                body = r.text
            raise RuntimeError(f"HTTP {r.status_code}: {body}")
        if r.content:
            if isinstance(ctype, str) and ctype.startswith("application/json"):
                return r.json()
            return r.text
        return None
