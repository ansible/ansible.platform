# -*- coding: utf-8 -*-
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any
import os, sys, time, datetime

DEBUG_TRACE = os.environ.get("AAP_AGENT_TRACE", "0") == "1"

def trace(msg: str):
    if not DEBUG_TRACE:
        return
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[TRACE {ts}] repos.user: {msg}"
    print(line, file=sys.stderr, flush=True)
    try:
        with open("/tmp/aap_agent_debug.log", "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

class BaseAPI(ABC):
    """
    Version façade base. Repos call these helpers to avoid hardcoding paths.
    Concrete versions (API25, API26, …) override paths/munging as needed.
    """

    # ---- Users ----
    @abstractmethod
    def user_list_path(self) -> str: ...
    @abstractmethod
    def user_detail_path(self, user_id: str) -> str: ...

    def normalize_user_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hook to adapt field names/required keys across versions.
        Default: pass-through.
        """
        return payload
