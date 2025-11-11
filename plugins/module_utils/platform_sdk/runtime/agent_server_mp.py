# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, json, time, signal, datetime, threading
from http.server import ThreadingHTTPServer as HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Optional, Any, List
import multiprocessing as mp
import requests

# =========================================================
# Tracing (toggle with: export AAP_AGENT_TRACE=1)
# =========================================================
DEBUG_TRACE = os.environ.get("AAP_AGENT_TRACE", "0") == "1"

def trace(msg: str):
    if not DEBUG_TRACE:
        return
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[TRACE {ts}] agent_server_mp: {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        with open("/tmp/aap_agent_debug.log", "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

# =========================================================
# Helpers
# =========================================================
def _norm_base(b: str) -> str:
    """Normalize base URL as dictionary key (no trailing slash)."""
    return (b or "").rstrip("/")

# =========================================================
# Shared state via Manager
# =========================================================
def _new_manager_state():
    """
    Returns (manager, state_dict).
    state[base] = {
        "verify": True|False|"/path/ca.pem",
        "token": "....",
        "expiry": float_epoch,
        "cache": manager.dict({ (kind, scope, name): (id, expiry) })
    }
    """
    manager = mp.Manager()
    state = manager.dict()
    trace("Manager and shared state initialized")
    return manager, state

# =========================================================
# Per-base worker process
# =========================================================
def _worker_loop(base: str, state: Dict[str, Any], req_q: mp.Queue, resp_q: mp.Queue):
    """
    Dedicated process for a given base URL. Holds a persistent requests.Session
    (enables TCP keep-alive, TLS session reuse, cookies, etc.).
    """
    base = _norm_base(base)
    sess = requests.Session()
    trace(f"MW[{base}] started (PID={os.getpid()})")

    def _resolve_verify(v) -> bool | str:
        if isinstance(v, bool):
            return v
        if isinstance(v, str) and v.strip():
            # treat non-empty string as CA path
            return v
        return True

    def _get_cfg():
        # read current config from Manager state
        b = state.get(base, {})
        verify = _resolve_verify(b.get("verify", True))
        token  = b.get("token", "")
        expiry = float(b.get("expiry", 0.0))
        return verify, token, expiry

    def _ensure_token():
        # hook for future refresh (when we have /refresh)
        _verify, token, expiry = _get_cfg()
        # we could refresh when time.time() > expiry-30
        return token

    def _do_one(method: str, path: str, params=None, json_body=None, headers=None):
        verify, _token, _ = _get_cfg()
        token = _ensure_token()
        req_headers = {"Accept": "application/json", "User-Agent": "ansible.platform-agent-mp/0.1"}
        if headers:
            req_headers.update(headers)
        if token:
            req_headers["Authorization"] = f"Bearer {token}"

        url = f"{base}{path}"  # base is normalized (no trailing /); path should start with /
        from urllib.parse import urlencode
        if params:
            trace(f"MW[{base}] → {method} {url}?{urlencode(params, doseq=True)}")
        else:
            trace(f"MW[{base}] → {method} {url}")

        r = sess.request(method=method, url=url, params=params, json=json_body,
                         headers=req_headers, timeout=30, verify=verify)

        ctype = r.headers.get("Content-Type", "")
        trace(f"MW[{base}] ← {r.status_code} {url}")
        if r.status_code >= 400:
            # structured error back to server
            try:
                body = r.json() if isinstance(ctype, str) and ctype.startswith("application/json") else r.text
            except Exception:
                body = r.text
            return r.status_code, body

        if r.content:
            if isinstance(ctype, str) and ctype.startswith("application/json"):
                return r.status_code, r.json()
            return r.status_code, r.text
        return r.status_code, None

    while True:
        msg = req_q.get()
        if msg is None:
            trace(f"MW[{base}] got sentinel → exit")
            break

        mid = msg.get("id", "")
        try:
            op = msg.get("op", "REQUEST")
            if op == "PING":
                resp_q.put({"id": mid, "ok": True, "status": 200, "data": {"pong": True}, "error": None})
                continue

            if op == "REQUEST":
                st, data = _do_one(
                    method=msg.get("method", "GET"),
                    path=msg.get("path", "/"),
                    params=msg.get("params"),
                    json_body=msg.get("json"),
                    headers=msg.get("headers"),
                )
                resp_q.put({
                    "id": mid, "ok": st < 400, "status": st,
                    "data": data if st < 400 else None,
                    "error": None if st < 400 else str(data)
                })
                continue

            if op == "BULK":
                jobs = msg.get("jobs") or []
                results: List[Dict[str, Any]] = []
                worst = 200
                for j in jobs:
                    st, data = _do_one(
                        method=j.get("method", "GET"),
                        path=j.get("path", "/"),
                        params=j.get("params"),
                        json_body=j.get("json"),
                        headers=j.get("headers"),
                    )
                    results.append({
                        "status": st,
                        "data": (data if st < 400 else None),
                        "error": (None if st < 400 else str(data))
                    })
                    if st > worst:
                        worst = st
                resp_q.put({
                    "id": mid, "ok": worst < 400, "status": worst,
                    "data": results,
                    "error": None if worst < 400 else "one or more jobs failed"
                })
                continue

            # unknown op
            resp_q.put({"id": mid, "ok": False, "status": 400, "data": None, "error": f"unknown op {op}"})
        except Exception as e:
            trace(f"MW[{base}] exception: {e}")
            resp_q.put({"id": mid, "ok": False, "status": 500, "data": None, "error": str(e)})

# =========================================================
# Agent supervisor (HTTP side)
# =========================================================
class Agent:
    def __init__(self):
        self.manager, self.state = _new_manager_state()
        # base -> {"proc": Process, "req": Queue, "resp": Queue}
        self.workers: Dict[str, Dict[str, Any]] = {}
        trace("Agent supervisor constructed")

    def _ensure_base_entry(self, base: str):
        base = _norm_base(base)
        if base not in self.state:
            self.state[base] = {
                "verify": True,
                "token": "",
                "expiry": 0.0,
                "cache": self.manager.dict(),
            }
            trace(f"State entry created for base={base}")

    def set_verify(self, base: str, verify: Any):
        base = _norm_base(base)
        self._ensure_base_entry(base)
        b = self.state[base]
        b["verify"] = verify
        self.state[base] = b
        trace(f"set_verify base={base} verify={verify}")

    def set_token(self, base: str, token: str, expiry: float):
        base = _norm_base(base)
        self._ensure_base_entry(base)
        b = self.state[base]
        b["token"] = token
        b["expiry"] = float(expiry)
        self.state[base] = b
        trace(f"set_token base={base} expiry={expiry}")

    # --- cache helpers ---
    def cache_get(self, base: str, kind: str, scope: str, name: str) -> Optional[str]:
        base = _norm_base(base)
        self._ensure_base_entry(base)
        cache = self.state[base]["cache"]
        k = (kind, scope, name)
        v = cache.get(k)
        if not v:
            return None
        id_, expiry = v
        if time.time() >= float(expiry):
            cache.pop(k, None)
            return None
        return id_

    def cache_put(self, base: str, kind: str, scope: str, name: str, id_: str, ttl: Optional[int]):
        base = _norm_base(base)
        self._ensure_base_entry(base)
        cache = self.state[base]["cache"]
        ttl = float(ttl if ttl is not None else 300)
        cache[(kind, scope, name)] = (id_, time.time() + ttl)

    def cache_flush(self, base: str, kind: Optional[str], scope: Optional[str]):
        base = _norm_base(base)
        self._ensure_base_entry(base)
        cache = self.state[base]["cache"]
        if not kind and not scope:
            cache.clear()
            return
        to_del = []
        for (k_kind, k_scope, k_name), _v in list(cache.items()):
            if (not kind or k_kind == kind) and (not scope or k_scope == scope):
                to_del.append((k_kind, k_scope, k_name))
        for k in to_del:
            cache.pop(k, None)

    def _ensure_worker(self, base: str):
        # it will simply find the existing entry in self.workers and skip spawning.
        base = _norm_base(base)
        if base in self.workers:
            return
        req_q: mp.Queue = mp.Queue()
        resp_q: mp.Queue = mp.Queue()
        p = mp.Process(target=_worker_loop, args=(base, self.state, req_q, resp_q), daemon=True)
        p.start()
        self.workers[base] = {"proc": p, "req": req_q, "resp": resp_q}
        trace(f"Spawned MW for base={base} (PID={p.pid})")

    def _rpc(self, base: str, payload: Dict[str, Any], timeout: float = 60.0) -> Dict[str, Any]:
        base = _norm_base(base)
        self._ensure_worker(base)
        q_req = self.workers[base]["req"]
        q_rsp = self.workers[base]["resp"]
        rid = str(time.time_ns())
        payload = dict(payload)
        payload["id"] = rid
        trace(f"RPC→ base={base} op={payload.get('op')} id={rid}")
        q_req.put(payload)

        # bounded wait to avoid infinite hangs
        end = time.time() + timeout
        while True:
            remaining = end - time.time()
            if remaining <= 0:
                trace(f"RPC timeout id={rid} base={base}")
                return {"id": rid, "ok": False, "status": 504, "data": None, "error": "gateway timeout waiting for worker"}
            try:
                msg = q_rsp.get(timeout=min(remaining, 0.5))
                if msg.get("id") == rid:
                    trace(f"RPC← id={rid} ok={msg.get('ok')} status={msg.get('status')}")
                    return msg
            except Exception:
                # keep waiting until timeout
                pass

AGENT = Agent()

# =========================================================
# HTTP Handler
# =========================================================
class Handler(BaseHTTPRequestHandler):
    server_version = "AAPAgentMP/0.1"

    def _json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw or b"{}")
        except Exception:
            return {}

    def _send(self, code: int, payload, upstream_status: Optional[int] = None):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        if upstream_status is not None:
            self.send_header("X-Upstream-Status", str(upstream_status))
        self.end_headers()
        self.wfile.write(data)

    # ---- endpoints ----
    def do_GET(self):
        trace(f"HTTP GET {self.path}")
        if self.path == "/healthz":
            return self._send(200, {"ok": True})
        if self.path == "/shutdown":
            # CI-friendly graceful stop
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return self._send(200, {"ok": True})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        trace(f"HTTP POST {self.path}")
        if self.path == "/bootstrap":
            # {base, token, expiry, verify}
            body = self._json()
            base = _norm_base(body["base"])
            AGENT.set_verify(base, body.get("verify", True))
            tok = body.get("token")
            if tok:
                AGENT.set_token(base, tok, float(body.get("expiry", time.time() + 3600)))
            AGENT._ensure_worker(base)  # spin worker now so first /request is fast
            return self._send(200, {"ok": True})

        if self.path == "/request":
            # {base, method, path, params?, json?, headers?}
            body = self._json()
            base = _norm_base(body["base"])
            msg = {
                "op": "REQUEST",
                "method": body.get("method", "GET"),
                "path": body.get("path", "/"),
                "params": body.get("params"),
                "json": body.get("json"),
                "headers": body.get("headers"),
            }
            res = AGENT._rpc(base, msg)
            code = 200 if res.get("ok") else 502
            return self._send(
                code,
                {"status": res.get("status", 500), "data": res.get("data"), "error": res.get("error")},
                upstream_status=res.get("status"),
            )

        if self.path == "/bulk":
            # {base, jobs: [ {method, path, params?, json?, headers?}, ... ]}
            body = self._json()
            base = _norm_base(body["base"])
            jobs = body.get("jobs") or []
            msg = {"op": "BULK", "jobs": jobs}
            res = AGENT._rpc(base, msg)
            code = 200 if res.get("ok") else 502
            return self._send(
                code,
                {"status": res.get("status", 500), "data": res.get("data"), "error": res.get("error")},
                upstream_status=res.get("status"),
            )

        # cache ops
        if self.path == "/cache/get":
            body = self._json()
            base = _norm_base(body["base"])
            kind  = body.get("kind", "user")
            scope = body.get("scope", "")
            name  = body["name"]
            id_ = AGENT.cache_get(base, kind, scope, name)
            return self._send(200, {"id": id_})

        if self.path == "/cache/put":
            body = self._json()
            base = _norm_base(body["base"])
            kind  = body.get("kind", "user")
            scope = body.get("scope", "")
            name  = body["name"]
            id_   = body["id"]
            ttl   = body.get("ttl")
            AGENT.cache_put(base, kind, scope, name, id_, ttl)
            return self._send(200, {"ok": True})

        if self.path == "/cache/flush":
            body = self._json()
            base = _norm_base(body["base"])
            AGENT.cache_flush(base, body.get("kind"), body.get("scope"))
            return self._send(200, {"ok": True})

        return self._send(404, {"error": "not found"})

# =========================================================
# Boot
# =========================================================
def _graceful_shutdown(httpd: HTTPServer):
    def _handler(signum, _frame):
        trace(f"Signal {signum} → shutdown()")
        try:
            httpd.shutdown()
        except Exception:
            pass
    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

def run(addr: str = "127.0.0.1", port: int = 0):
    httpd = HTTPServer((addr, port), Handler)
    _graceful_shutdown(httpd)
    sa = httpd.socket.getsockname()
    print(json.dumps({"addr": sa[0], "port": sa[1]}), flush=True)  # banner for action plugin
    trace(f"Agent HTTP server listening at {sa[0]}:{sa[1]} (PID={os.getpid()})")
    httpd.serve_forever()

if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    trace(f"p = {p}")
    run("127.0.0.1", p)
