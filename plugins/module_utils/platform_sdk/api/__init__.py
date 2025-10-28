from .base import BaseAPI
from .v25 import API25
from .v26 import API26

def api_factory(version: str | None) -> BaseAPI:
    if not version:
        return API25()  # safe default
    if version.startswith("268"):
        return API26()
    return API25()
