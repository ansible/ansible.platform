# v26.py
from .base import BaseAPI

class API26(BaseAPI):
    def user_list_path(self) -> str:
        # maybe the path or required fields change in 2.6
        return "/api/gateway/v2/users/"
    def user_detail_path(self, user_id: str) -> str:
        return f"/api/gateway/v2/users/{user_id}/"
    def normalize_user_payload(self, payload):
        # adapt payload if 2.6 needs additional fields or naming
        return payload
