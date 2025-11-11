# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any
import os, sys, time, datetime

DEBUG_TRACE = os.environ.get("AAP_AGENT_TRACE", "0") == "1"

def trace(msg: str):
    if not DEBUG_TRACE:
        return
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[TRACE {ts}] handler.base.py: {msg}"
    print(line, file=sys.stderr, flush=True)
    
    try:
        with open("/tmp/aap_agent_debug.log", "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

def ensure_keys(d: Dict[str, Any], *keys: str):
    trace("keys → {keys}")
    for k in keys:
        if k not in d:
            raise ValueError(f"missing required param: {k}")
