# v25.py
from .base import BaseAPI

class API25(BaseAPI):
    def user_list_path(self) -> str:
        return "/api/gateway/v1/users/"
    def user_detail_path(self, user_id: str) -> str:
        return f"/api/gateway/v1/users/{user_id}/"
    def normalize_user_payload(self, payload):
        # if 2.5 has slightly different field names or constraints, map here
        return payload
