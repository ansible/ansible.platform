# plugins/module_utils/platform_sdk/repos/user.py
from __future__ import annotations
from typing import Iterable, Optional
import os, sys, time, datetime

from ..abc import Repository
from ..client import PlatformClient
from ..generated.user_models import User

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


class UsersRepo(Repository[User]):
    def __init__(self, client: PlatformClient):
        self.client = client

    def list(self) -> Iterable[User]:
        t0 = time.monotonic()
        trace("list → GET /api/gateway/v1/users/")
        data = self.client.request("GET", "/api/gateway/v1/users/")
        dt = (time.monotonic() - t0) * 1000.0
        items = data.get("results") or []
        trace(f"list ← {len(items)} users dt_ms={dt:.1f}")
        for item in items:
            yield User(
                id=item.get("id"),
                username=item.get("username"),
                email=item.get("email"),
                first_name=item.get("first_name") or "",
                last_name=item.get("last_name") or "",
                is_superuser=item.get("is_superuser") or False,
            )

    def get_by_name(self, name: str) -> Optional[User]:
        t0 = time.monotonic()
        trace(f"get_by_name('{name}') → GET /api/gateway/v1/users/?username={name}")
        data = self.client.request("GET", "/api/gateway/v1/users/", params={"username": name})
        dt = (time.monotonic() - t0) * 1000.0
        items = data.get("results") or []
        trace(f"get_by_name('{name}') ← {len(items)} match(es) dt_ms={dt:.1f}")
        if not items:
            return None
        u = items[0]
        return User(
            id=u.get("id"),
            username=u.get("username"),
            email=u.get("email"),
            first_name=u.get("first_name") or "",
            last_name=u.get("last_name") or "",
            is_superuser=u.get("is_superuser") or False,
        )

    def create(self, obj: User) -> User:
        payload = {
            "username": obj.username,
            "email": obj.email,
            "first_name": obj.first_name,
            "last_name": obj.last_name,
            "is_superuser": obj.is_superuser,
        }
        t0 = time.monotonic()
        trace(f"create('{obj.username}') → POST /api/gateway/v1/users/ body={{...}}")
        u = self.client.request("POST", "/api/gateway/v1/users/", json_body=payload)
        dt = (time.monotonic() - t0) * 1000.0
        trace(f"create('{obj.username}') ← id={u.get('id')} dt_ms={dt:.1f}")
        return User(
            id=u.get("id"),
            username=u.get("username"),
            email=u.get("email"),
            first_name=u.get("first_name") or "",
            last_name=u.get("last_name") or "",
            is_superuser=u.get("is_superuser") or False,
        )

    def update(self, obj: User) -> User:
        assert obj.id, "update requires id"
        payload = {
            "email": obj.email,
            "first_name": obj.first_name,
            "last_name": obj.last_name,
            "is_superuser": obj.is_superuser,
        }
        t0 = time.monotonic()
        trace(f"update(id={obj.id}) → PATCH /api/gateway/v1/users/{obj.id}/ body={{...}}")
        u = self.client.request("PATCH", f"/api/gateway/v1/users/{obj.id}/", json_body=payload)
        dt = (time.monotonic() - t0) * 1000.0
        trace(f"update(id={obj.id}) ← OK dt_ms={dt:.1f}")
        return User(
            id=u.get("id"),
            username=u.get("username"),
            email=u.get("email"),
            first_name=u.get("first_name") or "",
            last_name=u.get("last_name") or "",
            is_superuser=u.get("is_superuser") or False,
        )

    def delete(self, obj: User) -> None:
        assert obj.id, "delete requires id"
        t0 = time.monotonic()
        trace(f"delete(id={obj.id}) → DELETE /api/gateway/v1/users/{obj.id}/")
        self.client.request("DELETE", f"/api/gateway/v1/users/{obj.id}/")
        dt = (time.monotonic() - t0) * 1000.0
        trace(f"delete(id={obj.id}) ← OK dt_ms={dt:.1f}")
