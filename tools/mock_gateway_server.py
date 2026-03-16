"""
Local mock server for AAP Gateway API.

Purpose
-------
Gateway API v2 does not exist (yet), but we still want to validate our-side
multi-version routing/selection and isolation behavior for ANSTRAT-1640.

This server implements a minimal subset of endpoints used by the POC:
  - GET /api/gateway/v1/ping/
  - GET /api/gateway/v2/ping/
  - GET/POST /api/gateway/v{1,2}/users/
  - GET/PATCH/DELETE /api/gateway/v{1,2}/users/{id}/
  - GET/POST /api/gateway/v{1,2}/organizations/
  - GET/PATCH/DELETE /api/gateway/v{1,2}/organizations/{id}/

Notes
-----
- Auth is intentionally permissive: if an Authorization header is present, we accept it.
  This keeps the mock focused on client behavior, not auth correctness.
- Data is stored in-memory and resets on restart.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse


def _now_iso() -> str:
    # Good enough for test output
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class Store:
    lock: threading.Lock = field(default_factory=threading.Lock)
    next_user_id: int = 1000
    next_org_id: int = 1000
    users: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    # Pre-seed orgs used by lookup logic (name -> id); dynamic orgs added here too
    orgs_by_id: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    orgs_by_name: Dict[str, int] = field(default_factory=dict)

    def seed_defaults(self) -> None:
        with self.lock:
            if self.orgs_by_id:
                return
            # Minimal org objects for name/id lookup.
            default_orgs = [
                {"id": 1, "name": "Default"},
                {"id": 2, "name": "Engineering"},
                {"id": 3, "name": "DevOps"},
            ]
            for org in default_orgs:
                self.orgs_by_id[org["id"]] = org
                self.orgs_by_name[org["name"]] = org["id"]

    def create_user(self, version: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            user_id = self.next_user_id
            self.next_user_id += 1

            username = payload.get("username")
            if not username:
                raise ValueError("username is required")

            user = {
                "id": user_id,
                "username": username,
                "email": payload.get("email"),
                "first_name": payload.get("first_name", ""),
                "last_name": payload.get("last_name", ""),
                "is_superuser": payload.get("is_superuser", False),
                "is_platform_auditor": payload.get("is_platform_auditor", False),
                "created": _now_iso(),
                "modified": _now_iso(),
                "url": f"/api/gateway/v{version}/users/{user_id}/",
                # mimic redaction in real outputs
                "password": "$encrypted$" if payload.get("password") else None,
            }
            self.users[user_id] = user
            return user

    def list_users(self, username: Optional[str] = None) -> Dict[str, Any]:
        with self.lock:
            items = list(self.users.values())
            if username:
                items = [u for u in items if u.get("username") == username]
            return {"count": len(items), "results": items}

    def get_user(self, user_id: int) -> Dict[str, Any]:
        with self.lock:
            if user_id not in self.users:
                raise KeyError("not found")
            return self.users[user_id]

    def patch_user(self, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            if user_id not in self.users:
                raise KeyError("not found")
            user = dict(self.users[user_id])
            for k, v in payload.items():
                # allow patch of known fields only (keep it simple)
                if k in {
                    "username",
                    "email",
                    "first_name",
                    "last_name",
                    "password",
                    "is_superuser",
                    "is_platform_auditor",
                }:
                    user[k] = "$encrypted$" if k == "password" and v else v
            user["modified"] = _now_iso()
            self.users[user_id] = user
            return user

    def delete_user(self, user_id: int) -> None:
        with self.lock:
            if user_id not in self.users:
                raise KeyError("not found")
            del self.users[user_id]

    def find_orgs_by_name(self, name: str) -> Dict[str, Any]:
        self.seed_defaults()
        with self.lock:
            org_id = self.orgs_by_name.get(name)
            if not org_id:
                return {"count": 0, "results": []}
            return {"count": 1, "results": [self.orgs_by_id[org_id]]}

    def list_orgs(self, name: Optional[str] = None) -> Dict[str, Any]:
        self.seed_defaults()
        with self.lock:
            if name:
                org_id = self.orgs_by_name.get(name)
                if not org_id:
                    return {"count": 0, "results": []}
                return {"count": 1, "results": [self.orgs_by_id[org_id]]}
            return {"count": len(self.orgs_by_id), "results": list(self.orgs_by_id.values())}

    def get_org(self, org_id: int) -> Dict[str, Any]:
        self.seed_defaults()
        with self.lock:
            if org_id not in self.orgs_by_id:
                raise KeyError("not found")
            return self.orgs_by_id[org_id]

    def create_org(self, version: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.seed_defaults()
        with self.lock:
            org_name = payload.get("name")
            if not org_name:
                raise ValueError("name is required")
            if org_name in self.orgs_by_name:
                raise ValueError(f"Organization with name '{org_name}' already exists")
            org_id = self.next_org_id
            self.next_org_id += 1
            org = {
                "id": org_id,
                "name": org_name,
                "description": payload.get("description") or "",
                "created": _now_iso(),
                "modified": _now_iso(),
                "url": f"/api/gateway/v{version}/organizations/{org_id}/",
            }
            self.orgs_by_id[org_id] = org
            self.orgs_by_name[org_name] = org_id
            return org

    def patch_org(self, org_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.seed_defaults()
        with self.lock:
            if org_id not in self.orgs_by_id:
                raise KeyError("not found")
            org = dict(self.orgs_by_id[org_id])
            old_name = org["name"]
            for k in ("name", "description"):
                if k in payload:
                    org[k] = payload[k] if payload[k] is not None else ""
            if org["name"] != old_name:
                del self.orgs_by_name[old_name]
                self.orgs_by_name[org["name"]] = org_id
            org["modified"] = _now_iso()
            self.orgs_by_id[org_id] = org
            return org

    def delete_org(self, org_id: int) -> None:
        self.seed_defaults()
        with self.lock:
            if org_id not in self.orgs_by_id:
                raise KeyError("not found")
            org = self.orgs_by_id[org_id]
            name = org.get("name")
            if name:
                self.orgs_by_name.pop(name, None)
            del self.orgs_by_id[org_id]


class MockGatewayHandler(BaseHTTPRequestHandler):
    server_version = "MockGateway/0.1"

    # Populated from server instance
    store: Store
    reported_api_version: str

    def log_message(self, fmt: str, *args) -> None:
        # Reduce noise; comment out if you want request logs.
        return

    def _send_json(self, code: int, payload: Any, headers: Optional[Dict[str, str]] = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_empty(self, code: int) -> None:
        self.send_response(code)
        self.end_headers()

    def _require_auth(self) -> bool:
        # Very permissive: accept any Authorization header
        return bool(self.headers.get("Authorization"))

    def _parse_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _route(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query or "")

        # Health check (no auth) for Molecule create/destroy lifecycle
        if path in ("/health", "/health/") and self.command == "GET":
            self._send_json(200, {"status": "ok"})
            return

        # Auth: return 401 if missing header (matches our client expectations enough)
        if not self._require_auth():
            self._send_json(401, {"detail": "Missing Authorization header"})
            return

        # Match /api/gateway/ (version discovery - used by PlatformService._detect_api_version)
        parts = [p for p in path.split("/") if p]
        if len(parts) == 2 and parts[0] == "api" and parts[1] == "gateway" and self.command == "GET":
            v = self.reported_api_version
            self._send_json(200, {
                "current_version": f"/api/gateway/v{v}/",
                "available_versions": {"v1": "/api/gateway/v1/", "v2": "/api/gateway/v2/"},
            })
            return

        # Match /api/gateway/v{n}/...
        if len(parts) < 3 or parts[0] != "api" or parts[1] != "gateway":
            self._send_json(404, {"detail": "Not Found"})
            return

        version_part = parts[2]  # e.g. v1, v2
        if not version_part.startswith("v"):
            self._send_json(404, {"detail": "Not Found"})
            return
        version = version_part[1:]

        # /api/gateway/vX/ping/
        if len(parts) == 4 and parts[3] == "ping" and self.command == "GET":
            headers = {"X-API-Version": self.reported_api_version}
            self._send_json(200, {"version": self.reported_api_version}, headers=headers)
            return

        # /api/gateway/vX/users/
        if len(parts) == 4 and parts[3] == "users":
            if self.command == "GET":
                username = (qs.get("username") or [None])[0]
                self._send_json(200, self.store.list_users(username=username))
                return
            if self.command == "POST":
                try:
                    payload = self._parse_json_body()
                    created = self.store.create_user(version=version, payload=payload)
                    self._send_json(201, created)
                except ValueError as e:
                    self._send_json(400, {"detail": str(e)})
                return

        # /api/gateway/vX/users/{id}/
        if len(parts) == 5 and parts[3] == "users":
            try:
                user_id = int(parts[4])
            except ValueError:
                self._send_json(404, {"detail": "Not Found"})
                return

            if self.command == "GET":
                try:
                    self._send_json(200, self.store.get_user(user_id))
                except KeyError:
                    self._send_json(404, {"detail": "Not Found"})
                return
            if self.command == "PATCH":
                try:
                    payload = self._parse_json_body()
                    self._send_json(200, self.store.patch_user(user_id, payload))
                except KeyError:
                    self._send_json(404, {"detail": "Not Found"})
                return
            if self.command == "DELETE":
                try:
                    self.store.delete_user(user_id)
                    self._send_empty(204)
                except KeyError:
                    self._send_json(404, {"detail": "Not Found"})
                return

        # /api/gateway/vX/organizations/
        if len(parts) == 4 and parts[3] == "organizations":
            if self.command == "GET":
                name = (qs.get("name") or [None])[0]
                self._send_json(200, self.store.list_orgs(name=name))
                return
            if self.command == "POST":
                try:
                    payload = self._parse_json_body()
                    created = self.store.create_org(version=version, payload=payload)
                    self._send_json(201, created)
                except ValueError as e:
                    self._send_json(400, {"detail": str(e)})
                return

        # /api/gateway/vX/organizations/{id}/
        if len(parts) == 5 and parts[3] == "organizations":
            try:
                org_id = int(parts[4])
            except ValueError:
                self._send_json(404, {"detail": "Not Found"})
                return
            if self.command == "GET":
                try:
                    self._send_json(200, self.store.get_org(org_id))
                except KeyError:
                    self._send_json(404, {"detail": "Not Found"})
                return
            if self.command == "PATCH":
                try:
                    payload = self._parse_json_body()
                    self._send_json(200, self.store.patch_org(org_id, payload))
                except KeyError:
                    self._send_json(404, {"detail": "Not Found"})
                return
            if self.command == "DELETE":
                try:
                    self.store.delete_org(org_id)
                    self._send_empty(204)
                except KeyError:
                    self._send_json(404, {"detail": "Not Found"})
                return

        self._send_json(404, {"detail": "Not Found"})

    def do_GET(self) -> None:  # noqa: N802
        self._route()

    def do_POST(self) -> None:  # noqa: N802
        self._route()

    def do_PATCH(self) -> None:  # noqa: N802
        self._route()

    def do_DELETE(self) -> None:  # noqa: N802
        self._route()


class MockGatewayServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, *, store: Store, reported_api_version: str):
        super().__init__(server_address, RequestHandlerClass)
        self.store = store
        self.reported_api_version = reported_api_version


def main() -> int:
    parser = argparse.ArgumentParser(description="Mock AAP Gateway API server (v1 + mocked v2).")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument(
        "--reported-api-version",
        default="1",
        help="Version reported by /api/gateway/v1/ping/ via X-API-Version and JSON (default: 1)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Daemonize: fork and print child PID to stdout (for Molecule create/destroy).",
    )
    args = parser.parse_args()

    store = Store()
    store.seed_defaults()

    # Inject store + version into handler via class attributes.
    MockGatewayHandler.store = store
    MockGatewayHandler.reported_api_version = str(args.reported_api_version)

    httpd = MockGatewayServer(
        (args.host, args.port),
        MockGatewayHandler,
        store=store,
        reported_api_version=str(args.reported_api_version),
    )

    if args.daemon:
        import os
        pid = os.fork()
        if pid:
            # Parent: print child PID and exit (Molecule captures stdout for PID)
            print(str(pid))
            return 0
        # Child: serve (stdout may be closed; avoid print)
        httpd.serve_forever()
        return 0

    print(f"Mock Gateway listening on http://{args.host}:{args.port} (reported_api_version={args.reported_api_version})")
    print("Endpoints: /health, /api/gateway/v{1,2}/ping/, /api/gateway/v{1,2}/users/, /api/gateway/v{1,2}/organizations/")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
