# -*- coding: utf-8 -*-
from __future__ import annotations
from .base import BaseAPI
from .v25 import API25
from .v26 import API26

def api_factory(version: str | None) -> BaseAPI:
    """
    Accepts version strings like "2.5.3", "2.6.0", "2.6", "unknown", None.
    Falls back to API25 when unknown.
    """
    if not version:
        return API25()
    v = version.strip().lower()
    # very forgiving parsing
    if v.startswith("2.6"):
        return API26()
    return API25()
