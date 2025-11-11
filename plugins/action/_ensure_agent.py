# plugins/action/_ensure_agent.py
from __future__ import annotations
import os, sys, json, time, subprocess, tempfile, datetime
from contextlib import contextmanager

DEBUG_TRACE = os.environ.get("AAP_AGENT_TRACE", "0") == "1"
WARMUP_SECS = float(os.environ.get("AAP_AGENT_WARMUP_SECS", "3.0"))

ADDRFILE = "/tmp/aap_agent.addr"   # now stores {"addr","port","authkey"}
LOCKFILE = "/tmp/aap_agent.lock"

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

def _read_addrfile() -> dict | None:
    try:
        with open(ADDRFILE, "r") as f:
            info = json.load(f)
        if not info.get("addr") or "port" not in info or not info.get("authkey"):
            return None
        return info
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

# ---- BaseManager client helpers ----
def _connect(info: dict):
    from multiprocessing.managers import BaseManager
    class AgentManager(BaseManager): ...
    AgentManager.register("Agent")
    addr = (info["addr"], int(info["port"]))
    authkey = bytes.fromhex(info["authkey"].strip())   # <— trim
    mgr = AgentManager(address=addr, authkey=authkey)
    mgr.connect()
    return mgr, mgr.Agent()

def _alive(info: dict, tries: int = 3, delay: float = 0.15) -> bool:
    for _ in range(max(1, tries)):
        try:
            _mgr, agent = _connect(info)
            pong = agent.ping()
            if isinstance(pong, dict) and pong.get("ok"):
                return True
        except Exception:
            pass
        time.sleep(delay)
    return False

def _wait_ready(info: dict, seconds: float) -> bool:
    deadline = time.time() + max(0.0, seconds)
    while time.time() < deadline:
        if _alive(info, tries=1, delay=0.10):
            return True
    return False

def _bootstrap(info: dict, base: str, token: str | None, verify):
    """Initialize per-base settings on the shared Agent via proxy calls."""
    _mgr, agent = _connect(info)
    base = (base or "").rstrip("/")
    if verify is not None:
        agent.set_verify(base, verify)
    if token:
        # give a simple 1h lease like before; agent can refresh in future
        agent.set_token(base, token, float(time.time() + 3600.0))
    # optional warm path so first request is fast (creates session/cache)
    agent.ensure_base(base)

def ensure_agent(py_exe: str, agent_path: str, base: str, token: str | None, verify) -> str:
    """
    Ensure a single persistent local Agent Manager is running and bootstrapped.
    Returns "addr:port" (and exports AAP_AGENT_AUTHKEY in the environment).
    """
    trace("ensure_agent: start (BaseManager)")

    # Fast path: use existing manager if healthy
    info = _read_addrfile()
    if info:
        ok = _alive(info)
        trace(f"addrfile -> {info}, alive={ok}")
        if not ok and _wait_ready(info, WARMUP_SECS):
            ok = True
        if ok:
            _bootstrap(info, base, token, verify)
            os.environ["AAP_AGENT_ADDR"] = f"{info['addr']}:{info['port']}"
            os.environ["AAP_AGENT_AUTHKEY"] = info["authkey"]
            return f"{info['addr']}:{info['port']}"

    # Slow path with lock: spawn manager once
    with _lock():
        info = _read_addrfile()
        if info:
            ok = _alive(info)
            trace(f"inside lock recheck -> alive={ok}")
            if not ok and _wait_ready(info, WARMUP_SECS):
                ok = True
            if ok:
                _bootstrap(info, base, token, verify)
                os.environ["AAP_AGENT_ADDR"] = f"{info['addr']}:{info['port']}"
                os.environ["AAP_AGENT_AUTHKEY"] = info["authkey"]
                return f"{info['addr']}:{info['port']}"

        # spawn the manager server (prints banner JSON on stdout)
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        cmd = [py_exe, agent_path]
        trace(f"spawning manager: {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
            close_fds=True,
            start_new_session=True,
        )
        first = (proc.stdout.readline() or "").strip()
        try:
            proc.stdout.close()
        except Exception:
            pass
        if not first:
            # race? maybe someone else started it
            probe = _read_addrfile()
            if probe and (_alive(probe) or _wait_ready(probe, WARMUP_SECS)):
                info = probe
            else:
                raise RuntimeError("Failed to start Agent manager: no banner")
        else:
            try:
                banner = json.loads(first)
                info = {"addr": banner["addr"], "port": int(banner["port"]), "authkey": banner["authkey"]}
                _write_addrfile_atomically(info)
            except Exception as e:
                raise RuntimeError(f"Invalid manager banner: {first}; {e}")

    # Finalize bootstrap & export env
    if not _alive(info) and not _wait_ready(info, WARMUP_SECS):
        raise RuntimeError("Agent manager failed readiness after start")

    _bootstrap(info, base, token, verify)
    os.environ["AAP_AGENT_ADDR"] = f"{info['addr']}:{info['port']}"
    os.environ["AAP_AGENT_AUTHKEY"] = info["authkey"]
    return f"{info['addr']}:{info['port']}"
