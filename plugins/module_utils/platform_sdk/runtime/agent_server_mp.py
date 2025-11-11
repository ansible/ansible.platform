# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, json, time, datetime
from typing import Dict, Optional, Any, List
import requests
from multiprocessing.managers import BaseManager

DEBUG_TRACE = os.environ.get("AAP_AGENT_TRACE", "0") == "1"

def trace(msg: str):
    if not DEBUG_TRACE:
        return
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[TRACE {ts}] agent_server_mp(BaseManager): {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        with open("/tmp/aap_agent_debug.log", "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

def _norm_base(b: str) -> str:
    return (b or "").rstrip("/")

class Agent:
    """
    Single shared Agent object living in the Manager server process.
    Holds per-base sessions/config, provides request/bulk/cache helpers.
    No HTTP server, no local queues — manager proxies call these directly.
    """
    def __init__(self):
        self._bases: Dict[str, Dict[str, Any]] = {}   # base -> config
        self._sessions: Dict[str, requests.Session] = {}
        self._cache: Dict[tuple, tuple] = {}          # (base, kind, scope, name) -> (id, expiry)
        trace("Agent singleton constructed")

    # ---- lifecycle / bootstrap ----
    def ping(self) -> Dict[str, Any]:
        return {"ok": True, "bases": list(self._bases.keys()), "cache_size": len(self._cache)}

    def ensure_base(self, base: str) -> None:
        base = _norm_base(base)
        if base not in self._bases:
            self._bases[base] = {"verify": True, "token": "", "expiry": 0.0}
            self._sessions[base] = requests.Session()
            trace(f"ensure_base: created entry for {base}")

    def set_verify(self, base: str, verify: Any) -> None:
        base = _norm_base(base)
        self.ensure_base(base)
        self._bases[base]["verify"] = verify
        trace(f"set_verify {base} -> {verify}")

    def set_token(self, base: str, token: str, expiry: float) -> None:
        base = _norm_base(base)
        self.ensure_base(base)
        self._bases[base]["token"] = token or ""
        self._bases[base]["expiry"] = float(expiry)
        trace(f"set_token {base} exp={expiry}")

    # ---- cache helpers (same API as before) ----
    def cache_get(self, base: str, kind: str, scope: str, name: str) -> Optional[str]:
        base = _norm_base(base)
        k = (base, kind, scope, name)
        v = self._cache.get(k)
        if not v:
            return None
        id_, expiry = v
        if time.time() >= float(expiry):
            self._cache.pop(k, None)
            return None
        return id_

    def cache_put(self, base: str, kind: str, scope: str, name: str, id_: str, ttl: Optional[int]):
        base = _norm_base(base)
        ttl = float(ttl if ttl is not None else 300.0)
        self._cache[(base, kind, scope, name)] = (id_, time.time() + ttl)

    def cache_flush(self, base: str, kind: Optional[str], scope: Optional[str]):
        base = _norm_base(base)
        if not kind and not scope:
            # flush everything for this base
            keys = [k for k in self._cache if k[0] == base]
            for k in keys: self._cache.pop(k, None)
            return
        to_del = []
        for (b, k_kind, k_scope, k_name), _v in list(self._cache.items()):
            if b != base:
                continue
            if (not kind or k_kind == kind) and (not scope or k_scope == scope):
                to_del.append((b, k_kind, k_scope, k_name))
        for k in to_del:
            self._cache.pop(k, None)

    # ---- upstream HTTP helpers (lives here, no extra worker/queue) ----
    def _resolve_verify(self, v) -> bool | str:
        if isinstance(v, bool): return v
        if isinstance(v, str) and v.strip(): return v
        return True

    def _get_cfg(self, base: str):
        b = self._bases.get(base) or {}
        return self._resolve_verify(b.get("verify", True)), b.get("token",""), float(b.get("expiry", 0.0))

    def request(self, base: str, method: str, path: str, params=None, json_body=None, headers=None) -> Dict[str, Any]:
        base = _norm_base(base)
        self.ensure_base(base)
        sess = self._sessions[base]
        verify, token, _ = self._get_cfg(base)
        url = f"{base}{path}"
        req_headers = {"Accept": "application/json", "User-Agent": "ansible.platform-agent-mp/0.2"}
        if headers: req_headers.update(headers)
        if token: req_headers["Authorization"] = f"Bearer {token}"

        from urllib.parse import urlencode
        trace(f"REQ[{base}] → {method} {url}{'?' + urlencode(params, doseq=True) if params else ''}")
        r = sess.request(method=method, url=url, params=params, json=json_body, headers=req_headers,
                         timeout=30, verify=verify)
        ctype = r.headers.get("Content-Type","") or ""
        trace(f"REQ[{base}] ← {r.status_code}")
        if r.status_code >= 400:
            try:
                body = r.json() if ctype.startswith("application/json") else r.text
            except Exception:
                body = r.text
            return {"ok": False, "status": r.status_code, "error": body, "data": None}
        if r.content:
            data = r.json() if ctype.startswith("application/json") else r.text
        else:
            data = None
        return {"ok": True, "status": r.status_code, "error": None, "data": data}

    def bulk(self, base: str, jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        base = _norm_base(base)
        results: List[Dict[str, Any]] = []
        worst = 200
        for j in (jobs or []):
            res = self.request(
                base=base,
                method=j.get("method","GET"),
                path=j.get("path","/"),
                params=j.get("params"),
                json_body=j.get("json"),
                headers=j.get("headers"),
            )
            results.append(res)
            if isinstance(res.get("status"), int) and res["status"] > worst:
                worst = res["status"]
        return {"ok": worst < 400, "status": worst, "error": None if worst < 400 else "one or more jobs failed", "data": results}

# ---- Manager wiring ----
AGENT = Agent()

class AgentManager(BaseManager): ...
AgentManager.register("Agent", callable=lambda: AGENT)

def run(addr: str = "127.0.0.1", port: int = 0):
    # random authkey for each run; printed in banner
    authkey = os.urandom(16)
    mgr = AgentManager(address=(addr, port), authkey=authkey)
    server = mgr.get_server()
    sa = server.address  # (host, port)
    print(json.dumps({"addr": sa[0], "port": sa[1], "authkey": authkey.hex()}), flush=True)
    trace(f"Agent Manager listening at {sa[0]}:{sa[1]} (PID={os.getpid()})")
    server.serve_forever()

if __name__ == "__main__":
    # no CLI args needed; keep a port arg for compatibility if passed
    try:
        p = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    except Exception:
        p = 0
    run("127.0.0.1", p)
