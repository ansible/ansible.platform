# plugins/action/_ensure_agent.py
from __future__ import annotations
import os, sys, json, time, subprocess, urllib.request, tempfile
from contextlib import contextmanager
import datetime

DEBUG_TRACE = os.environ.get("AAP_AGENT_TRACE", "0") == "1"
WARMUP_SECS = float(os.environ.get("AAP_AGENT_WARMUP_SECS", "3.0"))  # grace window for brand-new agent

def trace(msg: str):
    if not DEBUG_TRACE:
        return
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[TRACE {ts}] ensure_agent.py: {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        with open("/tmp/aap_agent_debug.log", "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

ADDRFILE = "/tmp/aap_agent.addr"
LOCKFILE = "/tmp/aap_agent.lock"

def _alive(addr: str, tries: int = 3, delay: float = 0.15) -> bool:
    url = f"http://{addr}/healthz"
    for _ in range(max(1, tries)):
        try:
            with urllib.request.urlopen(url, timeout=0.8) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(delay)
    return False

def _wait_healthy(addr: str, seconds: float) -> bool:
    deadline = time.time() + max(0.0, seconds)
    while time.time() < deadline:
        if _alive(addr, tries=1, delay=0.10):
            return True
    return False

def _read_addrfile() -> str | None:
    try:
        with open(ADDRFILE, "r") as f:
            info = json.load(f)
        host = info.get("addr")
        port = info.get("port")
        if not host or not port:
            return None
        return f"{host}:{port}"
    except Exception as e:
        trace(f"_read_addrfile: failed: {e}")
        return None

def _write_addrfile_atomically(info: dict) -> None:
    d = os.path.dirname(ADDRFILE) or "/tmp"
    with tempfile.NamedTemporaryFile("w", dir=d, delete=False) as tmp:
        json.dump(info, tmp)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, ADDRFILE)
    trace(f"_write_addrfile_atomically: wrote {info}")

@contextmanager
def _lock():
    fd = os.open(LOCKFILE, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if hasattr(os, "lockf"):
            os.lockf(fd, os.F_LOCK, 0)
        yield
    finally:
        try:
            if hasattr(os, "lockf"):
                os.lockf(fd, os.F_ULOCK, 0)
        finally:
            os.close(fd)

def _bootstrap(addr: str, base: str, token: str | None, verify):
    payload = {
        "base": (base or "").rstrip("/"),
        "token": token or "",
        "verify": verify,
        "expiry": time.time() + 3600,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=f"http://{addr}/bootstrap",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    trace(f"_bootstrap: POST /bootstrap base={payload['base']} verify={verify}")
    with urllib.request.urlopen(req, timeout=5) as r:
        if r.status != 200:
            raise RuntimeError(f"bootstrap failed: {r.status}")

def ensure_agent(py_exe: str, agent_path: str, base: str, token: str | None, verify) -> str:
    """
    Ensure a single persistent local agent (ephemeral port) is running and bootstrapped.
    Port-agnostic and race-tolerant. Keeps agent alive across tasks by redirecting stderr to DEVNULL.
    """
    trace("ensure_agent: start (port-agnostic)")

    # Fast path: if addrfile exists, give it a short warm-up to become healthy, then reuse.
    addr = _read_addrfile()
    if addr:
        ok = _alive(addr)
        trace(f"ensure_agent: addrfile -> {addr}, healthz={ok}")
        if not ok and _wait_healthy(addr, WARMUP_SECS):
            ok = True
        if ok:
            _bootstrap(addr, base, token, verify)
            return addr

    # Slow path with lock (avoid double-spawn)
    with _lock():
        # Re-check within the lock
        addr = _read_addrfile()
        if addr:
            ok = _alive(addr)
            trace(f"ensure_agent: inside lock recheck -> {addr}, healthz={ok}")
            if not ok and _wait_healthy(addr, WARMUP_SECS):
                ok = True
            if ok:
                _bootstrap(addr, base, token, verify)
                return addr

        # Spawn a new agent on an ephemeral port
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        def _spawn() -> tuple[str, dict]:
            cmd = [py_exe, agent_path]  # no fixed port
            trace(f"ensure_agent: spawning agent: {' '.join(cmd)}")
            # IMPORTANT: stderr -> DEVNULL so agent logs don't kill it after parent exits.
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,               # read banner once
                stderr=subprocess.DEVNULL,            # detach logging sink
                text=True,
                env=env,
                close_fds=True,
                start_new_session=True,
            )
            first = (proc.stdout.readline() or "").strip()
            # We don't need the pipe anymore; avoid holding fds
            try:
                proc.stdout.close()
            except Exception:
                pass

            if not first:
                return "", {"err": "no banner from agent"}
            try:
                info = json.loads(first)
                return f"{info['addr']}:{info['port']}", {"info": info}
            except Exception as e:
                return "", {"err": f"invalid banner: {first}; {e}"}

        addr, meta = _spawn()
        if not addr:
            # If we lost a race, reuse the addrfile winner (if healthy)
            probe = _read_addrfile()
            if probe and (_alive(probe) or _wait_healthy(probe, WARMUP_SECS)):
                trace("ensure_agent: spawn race → reusing newly alive agent")
                _bootstrap(probe, base, token, verify)
                return probe
            raise RuntimeError(f"Failed to start agent: {meta.get('err','unknown error')}")

        # Wait until /healthz OK (combine quick probes + warmup)
        if not _alive(addr, tries=10, delay=0.2) and not _wait_healthy(addr, WARMUP_SECS):
            raise RuntimeError("Agent failed health check after start")

        # Publish addrfile with banner info
        info = meta.get("info")
        if info:
            _write_addrfile_atomically(info)
        else:
            host, port = addr.split(":")
            _write_addrfile_atomically({"addr": host, "port": int(port)})

    # Final bootstrap (idempotent)
    _bootstrap(addr, base, token, verify)
    return addr
