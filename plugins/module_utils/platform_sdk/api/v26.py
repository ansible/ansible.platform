# -*- coding: utf-8 -*-
from __future__ import annotations
from .base import BaseAPI

class API26(BaseAPI):
    def user_list_path(self) -> str:
        return "/api/gateway/v2/users/"

    def user_detail_path(self, user_id: str) -> str:
        return f"/api/gateway/v2/users/{user_id}/"

    # Example override if 2.6 needed tweaks
    # def normalize_user_payload(self, payload):
    #     return payload
