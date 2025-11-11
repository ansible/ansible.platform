# -*- coding: utf-8 -*-
from __future__ import annotations
from .base import BaseAPI

class API25(BaseAPI):
    # Default (older) gateway layout
    def user_list_path(self) -> str:
        return "/api/gateway/v1/users/"

    def user_detail_path(self, user_id: str) -> str:
        return f"/api/gateway/v1/users/{user_id}/"
