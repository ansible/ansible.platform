"""
Local mock server for AAP Gateway API.

Purpose
-------
Provides a fully self-contained mock of the AAP Gateway REST API for Molecule
integration tests. No real AAP instance is required.

Supported endpoints (all under /api/gateway/v{1,2}/):
  ping, users, organizations, teams,
  applications, authenticators, authenticator_maps,
  ca_certificates, feature_flags, http_ports,
  role_definitions, role_team_assignments, role_user_assignments,
  routes, service_clusters, service_keys, service_nodes,
  service_types, services, tokens, ui_plugin_routes,
  settings (singleton), settings/all (flat dict read)

Notes
-----
- Auth is intentionally permissive: any Authorization header is accepted.
- Data is stored in-memory and resets on restart.
"""

from __future__ import annotations

import argparse
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Generic in-memory CRUD store for a single resource type
# ---------------------------------------------------------------------------


class GenericResource:
    """Thread-safe CRUD store for any named resource."""

    def __init__(
        self,
        resource_name: str,
        required_fields: Optional[List[str]] = None,
        start_id: int = 2000,
        patch_fields: Optional[List[str]] = None,
        post_only_fields: Optional[Dict[str, Callable[[], Any]]] = None,
        url_prefix: Optional[str] = None,
        associations: Optional[List[str]] = None,
        sub_resources: Optional[List[str]] = None,
    ):
        self.lock = threading.Lock()
        self.resource_name = resource_name
        self.required_fields: List[str] = required_fields or []
        self.patch_fields: Optional[List[str]] = patch_fields  # None = allow all
        # post_only_fields: generated on POST, returned in create response, never stored.
        # Simulates API-generated secrets like client_secret that are only visible once.
        self.post_only_fields: Dict[str, Callable[[], Any]] = post_only_fields or {}
        # url_prefix: full base path (e.g. "/api/controller/v2/inventories/") used to
        # build the "url" field and copies. None = legacy gateway pattern built from `version`.
        self.url_prefix: Optional[str] = url_prefix
        # associations: sub-endpoint names this resource supports (e.g. "instance_groups").
        self.associations: List[str] = associations or []
        # sub_resources: GET/POST/DELETE sub-endpoint names backed by an arbitrary
        # stored JSON blob per item (e.g. "survey_spec"), as opposed to associations'
        # id-reference-list semantics.
        self.sub_resources: List[str] = sub_resources or []
        self._sub_data: Dict[int, Dict[str, Any]] = {}
        self._next_id = start_id
        self._items: Dict[int, Dict[str, Any]] = {}

    def _build_url(self, version: str, item_id: int) -> str:
        if self.url_prefix:
            return f"{self.url_prefix}{item_id}/"
        return f"/api/gateway/v{version}/{self.resource_name}/{item_id}/"

    def create(self, version: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            for rf in self.required_fields:
                if not payload.get(rf):
                    raise ValueError(f"'{rf}' is required")
            item_id = self._next_id
            self._next_id += 1
            item: Dict[str, Any] = {
                "id": item_id,
                "created": _now_iso(),
                "modified": _now_iso(),
                "url": self._build_url(version, item_id),
            }
            item.update({k: v for k, v in payload.items() if v is not None})
            self._items[item_id] = item
            # post_only_fields are returned in the POST response but never stored.
            # On GET/PATCH the fields will be absent, matching real Gateway behaviour.
            response = dict(item)
            for field_name, generator in self.post_only_fields.items():
                response[field_name] = generator()
            return response

    def get_associations(self, item_id: int, field: str) -> List[int]:
        with self.lock:
            if item_id not in self._items:
                raise KeyError("not found")
            return list(self._items[item_id].get(f"_assoc_{field}", []))

    def set_association(self, item_id: int, field: str, ref_id: Any, associate: bool) -> bool:
        with self.lock:
            if item_id not in self._items:
                raise KeyError("not found")
            item = dict(self._items[item_id])
            key = f"_assoc_{field}"
            current = set(item.get(key, []))
            changed = False
            if associate and ref_id not in current:
                current.add(ref_id)
                changed = True
            elif not associate and ref_id in current:
                current.discard(ref_id)
                changed = True
            item[key] = sorted(current)
            item["modified"] = _now_iso()
            self._items[item_id] = item
            return changed

    def get_sub_resource(self, item_id: int, field: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            if item_id not in self._items:
                raise KeyError("not found")
            return self._sub_data.get(item_id, {}).get(field)

    def set_sub_resource(self, item_id: int, field: str, data: Dict[str, Any]) -> None:
        with self.lock:
            if item_id not in self._items:
                raise KeyError("not found")
            self._sub_data.setdefault(item_id, {})[field] = data

    def delete_sub_resource(self, item_id: int, field: str) -> None:
        with self.lock:
            if item_id not in self._items:
                raise KeyError("not found")
            self._sub_data.setdefault(item_id, {}).pop(field, None)

    def copy_item(self, item_id: int, version: str, new_name: str) -> Dict[str, Any]:
        with self.lock:
            if item_id not in self._items:
                raise KeyError("not found")
            if not new_name:
                raise ValueError("name is required for copy")
            new_id = self._next_id
            self._next_id += 1
            new_item = dict(self._items[item_id])
            new_item["id"] = new_id
            new_item["name"] = new_name
            new_item["created"] = _now_iso()
            new_item["modified"] = _now_iso()
            new_item["url"] = self._build_url(version, new_id)
            self._items[new_id] = new_item
            return dict(new_item)

    def list_items(self, filters: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        with self.lock:
            items = list(self._items.values())
            if filters:
                # AAPModule.get_one() sends "or__id=X&or__name=Y" to find an item by
                # either its numeric id or its name in a single request (OR semantics).
                # Separate these out from regular AND-filters.
                or_id_val: Optional[str] = None
                or_name_val: Optional[str] = None
                regular: Dict[str, str] = {}
                for k, v in filters.items():
                    if k == "or__id":
                        or_id_val = v
                    elif k in ("or__name", "or__slug"):
                        or_name_val = v
                    else:
                        regular[k] = v
                # Apply AND-filters first
                for k, v in regular.items():
                    items = [i for i in items if str(i.get(k, "")) == str(v)]
                # Apply OR-filter: match by numeric id OR by name
                if or_id_val is not None or or_name_val is not None:

                    def _or_match(item: Dict[str, Any]) -> bool:
                        if or_id_val is not None:
                            try:
                                if item.get("id") == int(or_id_val):
                                    return True
                            except (ValueError, TypeError):
                                pass
                        if or_name_val is not None:
                            if str(item.get("name", "")) == str(or_name_val):
                                return True
                        return False

                    items = [i for i in items if _or_match(i)]
            return {"count": len(items), "results": items}

    def get(self, item_id: int) -> Dict[str, Any]:
        with self.lock:
            if item_id not in self._items:
                raise KeyError("not found")
            return dict(self._items[item_id])

    def patch(self, item_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            if item_id not in self._items:
                raise KeyError("not found")
            item = dict(self._items[item_id])
            allowed = self.patch_fields
            for k, v in payload.items():
                if k in ("id", "created", "url"):
                    continue
                if allowed is None or k in allowed:
                    item[k] = v
            item["modified"] = _now_iso()
            self._items[item_id] = item
            return item

    def delete(self, item_id: int) -> None:
        with self.lock:
            if item_id not in self._items:
                raise KeyError("not found")
            del self._items[item_id]

    def seed(self, version: str, items: List[Dict[str, Any]]) -> None:
        """Pre-populate with seed data (used for orgs, feature_flags, etc.)."""
        for raw in items:
            item_id = raw.get("id", self._next_id)
            self._next_id = max(self._next_id, item_id + 1)
            item = {
                "id": item_id,
                "created": _now_iso(),
                "modified": _now_iso(),
                "url": f"/api/gateway/v{version}/{self.resource_name}/{item_id}/",
            }
            item.update(raw)
            self._items[item_id] = item


# ---------------------------------------------------------------------------
# Top-level Store — holds all resources
# ---------------------------------------------------------------------------


@dataclass
class Store:
    lock: threading.Lock = field(default_factory=threading.Lock)

    # Legacy explicit stores (kept for backward compatibility with existing scenarios)
    next_user_id: int = 1000
    next_org_id: int = 1000
    next_team_id: int = 1000
    users: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    orgs_by_id: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    orgs_by_name: Dict[str, int] = field(default_factory=dict)
    teams_by_id: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    # Settings singleton: flat key→value dict
    _settings: Dict[str, Any] = field(default_factory=dict)
    _settings_lock: threading.Lock = field(default_factory=threading.Lock)

    # Generic resource stores (keyed by endpoint name)
    _resources: Dict[str, GenericResource] = field(default_factory=dict)

    # Generic Controller-side resource stores (/api/controller/v2/{name}/).
    # Organizations are handled separately (see _route_controller) — Controller
    # mirrors the Gateway's org table via a shared ID space, so it reuses
    # orgs_by_id/orgs_by_name rather than a second independent store.
    _controller_resources: Dict[str, GenericResource] = field(default_factory=dict)

    def _init_controller_resources(self) -> None:
        """Create Controller-side (/api/controller/v2/) generic resource stores."""
        self._controller_resources["instance_groups"] = GenericResource(
            resource_name="instance_groups",
            required_fields=["name"],
            start_id=100,
            url_prefix="/api/controller/v2/instance_groups/",
        )
        self._controller_resources["inventories"] = GenericResource(
            resource_name="inventories",
            required_fields=["name", "organization"],
            start_id=5000,
            url_prefix="/api/controller/v2/inventories/",
            associations=["instance_groups", "input_inventories"],
        )
        self._controller_resources["hosts"] = GenericResource(
            resource_name="hosts",
            required_fields=["name", "inventory"],
            start_id=6000,
            url_prefix="/api/controller/v2/hosts/",
        )
        self._controller_resources["credentials"] = GenericResource(
            resource_name="credentials",
            required_fields=["name"],
            start_id=7000,
            url_prefix="/api/controller/v2/credentials/",
        )
        self._controller_resources["execution_environments"] = GenericResource(
            resource_name="execution_environments",
            required_fields=["name"],
            start_id=8000,
            url_prefix="/api/controller/v2/execution_environments/",
        )
        self._controller_resources["projects"] = GenericResource(
            resource_name="projects",
            required_fields=["name"],
            start_id=9000,
            url_prefix="/api/controller/v2/projects/",
        )
        self._controller_resources["notification_templates"] = GenericResource(
            resource_name="notification_templates",
            required_fields=["name"],
            start_id=10000,
            url_prefix="/api/controller/v2/notification_templates/",
        )
        self._controller_resources["inventory_sources"] = GenericResource(
            resource_name="inventory_sources",
            required_fields=["name", "inventory"],
            start_id=11000,
            url_prefix="/api/controller/v2/inventory_sources/",
            associations=["notification_templates_started", "notification_templates_success", "notification_templates_error"],
        )
        self._controller_resources["inventory_updates"] = GenericResource(
            resource_name="inventory_updates",
            required_fields=[],
            start_id=12000,
            url_prefix="/api/controller/v2/inventory_updates/",
        )
        self._controller_resources["unified_job_templates"] = GenericResource(
            resource_name="unified_job_templates",
            required_fields=["name"],
            start_id=13000,
            url_prefix="/api/controller/v2/unified_job_templates/",
        )
        self._controller_resources["labels"] = GenericResource(
            resource_name="labels",
            required_fields=["name"],
            start_id=14000,
            url_prefix="/api/controller/v2/labels/",
        )
        self._controller_resources["schedules"] = GenericResource(
            resource_name="schedules",
            required_fields=["name"],
            start_id=15000,
            url_prefix="/api/controller/v2/schedules/",
            associations=["credentials", "labels", "instance_groups"],
        )
        self._controller_resources["job_templates"] = GenericResource(
            resource_name="job_templates",
            required_fields=["name"],
            start_id=16000,
            url_prefix="/api/controller/v2/job_templates/",
        )
        self._controller_resources["jobs"] = GenericResource(
            resource_name="jobs",
            required_fields=[],
            start_id=17000,
            url_prefix="/api/controller/v2/jobs/",
        )
        self._controller_resources["groups"] = GenericResource(
            resource_name="groups",
            required_fields=["name", "inventory"],
            start_id=18000,
            url_prefix="/api/controller/v2/groups/",
            associations=["hosts", "children"],
        )
        self._controller_resources["workflow_job_templates"] = GenericResource(
            resource_name="workflow_job_templates",
            required_fields=["name"],
            start_id=19000,
            url_prefix="/api/controller/v2/workflow_job_templates/",
            associations=[
                "labels",
                "notification_templates_started",
                "notification_templates_success",
                "notification_templates_error",
                "notification_templates_approvals",
            ],
            sub_resources=["survey_spec"],
        )
        self._controller_resources["project_updates"] = GenericResource(
            resource_name="project_updates",
            required_fields=[],
            start_id=20000,
            url_prefix="/api/controller/v2/project_updates/",
        )
        self._controller_resources["workflow_jobs"] = GenericResource(
            resource_name="workflow_jobs",
            required_fields=[],
            start_id=21000,
            url_prefix="/api/controller/v2/workflow_jobs/",
        )

    def controller_resource(self, name: str) -> Optional[GenericResource]:
        return self._controller_resources.get(name)

    def _init_resources(self) -> None:
        """Create all generic resource stores with appropriate config."""
        # Applications: client_secret returned on POST only, never on GET/PATCH.
        self._resources["applications"] = GenericResource(
            resource_name="applications",
            required_fields=["name", "organization"],
            start_id=3000,
            post_only_fields={
                "client_id": lambda: secrets.token_hex(16),
                "client_secret": lambda: secrets.token_hex(32),
            },
        )
        defs: List[tuple] = [
            # (endpoint_name, required_fields, start_id)
            ("authenticators", ["name"], 3100),
            ("authenticator_maps", ["name", "authenticator"], 3200),
            ("ca_certificates", ["name"], 3300),
            ("feature_flags", ["name"], 3400),
            ("http_ports", ["name"], 3500),
            ("role_definitions", ["name"], 3600),
            ("role_team_assignments", [], 3700),
            ("role_user_assignments", [], 3800),
            ("routes", ["name"], 3900),
            ("service_clusters", ["name"], 4000),
            ("service_keys", ["name"], 4100),
            ("service_nodes", ["name"], 4200),
            ("service_types", ["name"], 4300),
            ("services", ["name"], 4400),
            ("tokens", [], 4500),
            ("ui_plugin_routes", ["name"], 4600),
        ]
        for endpoint, required, start_id in defs:
            self._resources[endpoint] = GenericResource(
                resource_name=endpoint,
                required_fields=required,
                start_id=start_id,
            )

    def resource(self, name: str) -> Optional[GenericResource]:
        return self._resources.get(name)

    def seed_defaults(self) -> None:
        with self.lock:
            if self.orgs_by_id:
                return
            default_orgs = [
                {"id": 1, "name": "Default"},
                {"id": 2, "name": "Engineering"},
                {"id": 3, "name": "DevOps"},
            ]
            for org in default_orgs:
                self.orgs_by_id[org["id"]] = org
                self.orgs_by_name[org["name"]] = org["id"]

        # Seed feature flags with runtime-toggleable flags
        ff_store = self._resources.get("feature_flags")
        if ff_store and not ff_store._items:
            flags = [
                {
                    "id": 3401,
                    "name": "FEATURE_EXAMPLE_ENABLED",
                    "value": "False",
                    "toggle_type": "run-time",
                    "condition": "boolean",
                    "description": "Example runtime feature flag",
                    "required": False,
                    "support_level": "DEVELOPER_PREVIEW",
                    "visibility": True,
                    "labels": [],
                },
                {
                    "id": 3402,
                    "name": "FEATURE_EXPERIMENTAL_UI",
                    "value": "False",
                    "toggle_type": "run-time",
                    "condition": "boolean",
                    "description": "Experimental UI features",
                    "required": False,
                    "support_level": "DEVELOPER_PREVIEW",
                    "visibility": True,
                    "labels": [],
                },
            ]
            ff_store.seed("1", flags)

        # Seed settings
        with self._settings_lock:
            if not self._settings:
                self._settings = {
                    "RUNTIME_FEATURE_FLAGS": "True",
                    "SESSION_COOKIE_AGE": 1800,
                    "MAX_PAGE_SIZE": 200,
                    "REMOTE_HOST_HEADERS": [],
                }

    # ------------------------------------------------------------------ Users
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
                if k in {"username", "email", "first_name", "last_name", "password", "is_superuser", "is_platform_auditor"}:
                    user[k] = "$encrypted$" if k == "password" and v else v
            user["modified"] = _now_iso()
            self.users[user_id] = user
            return user

    def delete_user(self, user_id: int) -> None:
        with self.lock:
            if user_id not in self.users:
                raise KeyError("not found")
            del self.users[user_id]

    # ---------------------------------------------------------- Organizations
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

    # --------------------------------------------------------------- Teams
    def create_team(self, version: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.seed_defaults()
        with self.lock:
            team_name = payload.get("name")
            org_id = payload.get("organization")
            if not team_name:
                raise ValueError("name is required")
            if org_id is None:
                raise ValueError("organization is required")
            if org_id not in self.orgs_by_id:
                raise ValueError("organization does not exist")
            team_id = self.next_team_id
            self.next_team_id += 1
            team = {
                "id": team_id,
                "name": team_name,
                "description": payload.get("description") or "",
                "organization": org_id,
                "created": _now_iso(),
                "modified": _now_iso(),
                "url": f"/api/gateway/v{version}/teams/{team_id}/",
            }
            self.teams_by_id[team_id] = team
            return team

    def list_teams(self, name: Optional[str] = None, organization: Optional[int] = None) -> Dict[str, Any]:
        with self.lock:
            items = list(self.teams_by_id.values())
            if name is not None:
                items = [t for t in items if t.get("name") == name]
            if organization is not None:
                items = [t for t in items if t.get("organization") == organization]
            return {"count": len(items), "results": items}

    def get_team(self, team_id: int) -> Dict[str, Any]:
        with self.lock:
            if team_id not in self.teams_by_id:
                raise KeyError("not found")
            return self.teams_by_id[team_id]

    def patch_team(self, team_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            if team_id not in self.teams_by_id:
                raise KeyError("not found")
            team = dict(self.teams_by_id[team_id])
            for k in ("name", "description", "organization"):
                if k in payload and payload[k] is not None:
                    team[k] = payload[k]
            team["modified"] = _now_iso()
            self.teams_by_id[team_id] = team
            return team

    def delete_team(self, team_id: int) -> None:
        with self.lock:
            if team_id not in self.teams_by_id:
                raise KeyError("not found")
            del self.teams_by_id[team_id]

    # --------------------------------------------------------------- Settings
    def get_settings_all(self) -> Dict[str, Any]:
        self.seed_defaults()
        with self._settings_lock:
            return dict(self._settings)

    def patch_settings(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.seed_defaults()
        with self._settings_lock:
            self._settings.update(payload)
            return dict(self._settings)

    def get_settings_list(self) -> Dict[str, Any]:
        """Return settings in list form (used by feature_flag runtime check)."""
        self.seed_defaults()
        with self._settings_lock:
            results = [{"key": k, "value": v} for k, v in self._settings.items()]
            return {"count": len(results), "results": results}


# ---------------------------------------------------------------------------
# HTTP Request Handler
# ---------------------------------------------------------------------------


class MockGatewayHandler(BaseHTTPRequestHandler):
    server_version = "MockGateway/0.1"

    store: Store
    reported_api_version: str

    # (source_resource, sub_action) -> target resource store name for
    # launch-trigger sub-actions (POST {source}/{id}/{sub_action}/).
    _LAUNCH_SUB_ACTIONS = {
        ("inventory_sources", "update"): "inventory_updates",
        ("job_templates", "launch"): "jobs",
        ("projects", "update"): "project_updates",
    }

    # Resource stores whose GET-by-id simulates a pending -> successful
    # lifecycle across the first two polls (see _advance_launch_job_poll).
    _POLLING_RESOURCES = ("inventory_updates", "jobs", "project_updates", "workflow_jobs")

    def log_message(self, fmt: str, *args) -> None:
        return  # suppress per-request noise

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
        return bool(self.headers.get("Authorization"))

    def _parse_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _advance_launch_job_poll(self, store: "GenericResource", item_id: int) -> Dict[str, Any]:
        """Advance a launched job's pending -> successful lifecycle on each GET-by-id poll.

        Used for both inventory_updates (inventory_source's /update/) and jobs
        (job_template's /launch/). Simulates a real Controller job staying pending
        across the first two polls before resolving, so wait/poll loops in tests
        actually poll more than once instead of the mock resolving synchronously
        on launch.
        """
        with store.lock:
            if item_id not in store._items:
                raise KeyError("not found")
            item = store._items[item_id]

            if item.get("finished"):
                return dict(item)

            item["_polls"] = item.get("_polls", 0) + 1
            if item["_polls"] >= 2:
                item["status"] = "successful"
                item["finished"] = _now_iso()
                item["modified"] = _now_iso()

            return dict(item)

    # ------------------------------------------------------------------
    # Generic CRUD helper
    # ------------------------------------------------------------------

    def _handle_generic_resource(self, resource_name: str, parts: list, version: str, qs: Dict[str, list]) -> bool:
        """
        Handle CRUD for any generic Gateway resource.
        Returns True if the request was handled, False otherwise.
        """
        store = self.store.resource(resource_name)
        if store is None:
            return False
        return self._handle_generic_resource_store(store, parts, version, qs)

    def _handle_generic_resource_store(self, store: "GenericResource", parts: list, version: str, qs: Dict[str, list]) -> bool:
        """
        Handle list/create/get/patch/delete for any generic resource store.
        Returns True if the request was handled, False otherwise.
        """
        # List / Create:  /api/{service}/vX/{resource}/
        if len(parts) == 4:
            if self.command == "GET":
                filters = {k: v[0] for k, v in qs.items() if v}
                self._send_json(200, store.list_items(filters or None))
                return True
            if self.command == "POST":
                try:
                    payload = self._parse_json_body()
                    created = store.create(version, payload)
                    self._send_json(201, created)
                except ValueError as e:
                    self._send_json(400, {"detail": str(e)})
                return True

        # Get / Patch / Delete:  /api/gateway/vX/{resource}/{id}/
        if len(parts) == 5:
            try:
                item_id = int(parts[4])
            except ValueError:
                self._send_json(404, {"detail": "Not Found"})
                return True
            if self.command == "GET":
                try:
                    if store.resource_name in self._POLLING_RESOURCES:
                        self._send_json(200, self._advance_launch_job_poll(store, item_id))
                    else:
                        self._send_json(200, store.get(item_id))
                except KeyError:
                    self._send_json(404, {"detail": "Not Found"})
                return True
            if self.command == "PATCH":
                try:
                    payload = self._parse_json_body()
                    self._send_json(200, store.patch(item_id, payload))
                except KeyError:
                    self._send_json(404, {"detail": "Not Found"})
                return True
            if self.command == "DELETE":
                try:
                    store.delete(item_id)
                    self._send_empty(204)
                except KeyError:
                    self._send_json(404, {"detail": "Not Found"})
                return True

        return False

    # ------------------------------------------------------------------
    # Controller router (/api/controller/v2/...)
    # ------------------------------------------------------------------

    def _route_controller(self, parts: list, qs: Dict[str, list]) -> None:
        if len(parts) < 3 or parts[2] != "v2":
            self._send_json(404, {"detail": "Not Found"})
            return

        resource = parts[3] if len(parts) >= 4 else None

        # Organizations: Controller mirrors the Gateway's org table via a shared
        # ID space (single unified-auth source of truth), so reuse that store
        # instead of a second independent one.
        if resource == "organizations":
            if len(parts) == 4 and self.command == "GET":
                name = (qs.get("name") or [None])[0]
                self._send_json(200, self.store.list_orgs(name=name))
                return
            if len(parts) == 5:
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
            self._send_json(404, {"detail": "Not Found"})
            return

        # unified_job_templates: real Controller is a polymorphic view over
        # job_templates/inventory_sources/projects/workflow_job_templates sharing
        # their IDs, not a separate table. GET (list, by name) unions those
        # concrete stores plus the dedicated unified_job_templates store itself
        # (kept for tests that only need an arbitrary launchable-looking fixture,
        # e.g. schedule's unified_job_template field, with no real /launch/
        # sub-action behind it). POST still creates directly in the dedicated
        # store, for that same fixture use case.
        if resource == "unified_job_templates" and len(parts) == 4 and self.command == "GET":
            name = (qs.get("name") or [None])[0]
            combined = []
            for backing in ("unified_job_templates", "job_templates", "inventory_sources"):
                backing_store = self.store.controller_resource(backing)
                if backing_store is None:
                    continue
                combined.extend(backing_store.list_items({"name": name} if name else None)["results"])
            self._send_json(200, {"count": len(combined), "results": combined})
            return

        store = self.store.controller_resource(resource) if resource else None
        if store is None:
            self._send_json(404, {"detail": "Not Found"})
            return

        # Association / copy sub-endpoint:  /api/controller/v2/{resource}/{id}/{field}/
        if len(parts) == 6:
            try:
                item_id = int(parts[4])
            except ValueError:
                self._send_json(404, {"detail": "Not Found"})
                return
            field = parts[5]

            if field == "copy":
                if self.command == "POST":
                    try:
                        payload = self._parse_json_body()
                        copied = store.copy_item(item_id, "2", payload.get("name"))
                        self._send_json(201, copied)
                    except KeyError:
                        self._send_json(404, {"detail": "Not Found"})
                    except ValueError as e:
                        self._send_json(400, {"detail": str(e)})
                    return
                self._send_json(404, {"detail": "Not Found"})
                return

            # Sub-resource endpoints backed by an arbitrary stored blob per item
            # (e.g. workflow_job_templates' survey_spec) — GET/compare/POST/DELETE,
            # as opposed to associations' id-reference-list semantics.
            if field in store.sub_resources:
                try:
                    if self.command == "GET":
                        data = store.get_sub_resource(item_id, field)
                        if data is None:
                            self._send_json(404, {"detail": "Not Found"})
                        else:
                            self._send_json(200, data)
                        return
                    if self.command == "POST":
                        payload = self._parse_json_body()
                        store.set_sub_resource(item_id, field, payload)
                        self._send_json(200, payload)
                        return
                    if self.command == "DELETE":
                        store.delete_sub_resource(item_id, field)
                        self._send_empty(204)
                        return
                except KeyError:
                    self._send_json(404, {"detail": "Not Found"})
                    return
                self._send_json(404, {"detail": "Not Found"})
                return

            # Launch-trigger sub-actions: POST {resource}/{id}/{field}/ creates a
            # new job-like item in a separate store (e.g. inventory_sources'
            # /update/ -> inventory_updates, job_templates' /launch/ -> jobs).
            # Stays pending across the first two GET-by-id polls (see
            # _advance_launch_job_poll) so wait/poll loops actually poll
            # more than once, instead of the mock resolving synchronously.
            launch_target = self._LAUNCH_SUB_ACTIONS.get((resource, field))
            if launch_target:
                if self.command == "POST":
                    try:
                        source = store.get(item_id)
                    except KeyError:
                        self._send_json(404, {"detail": "Not Found"})
                        return
                    target_store = self.store.controller_resource(launch_target)
                    launched = target_store.create(
                        "2",
                        {
                            "name": source.get("name"),
                            "inventory": source.get("inventory"),
                            "status": "pending",
                            "finished": None,
                            "_polls": 0,
                        },
                    )
                    self._send_json(202, launched)
                    return
                self._send_json(404, {"detail": "Not Found"})
                return

            if field in store.associations:
                if self.command == "GET":
                    try:
                        ids = store.get_associations(item_id, field)
                        self._send_json(200, {"count": len(ids), "results": [{"id": i} for i in ids]})
                    except KeyError:
                        self._send_json(404, {"detail": "Not Found"})
                    return
                if self.command == "POST":
                    try:
                        payload = self._parse_json_body()
                        ref_id = payload.get("id")
                        associate = bool(payload.get("associate")) and not payload.get("disassociate")
                        store.set_association(item_id, field, ref_id, associate)
                        self._send_empty(204)
                    except KeyError:
                        self._send_json(404, {"detail": "Not Found"})
                    return

            self._send_json(404, {"detail": "Not Found"})
            return

        if self._handle_generic_resource_store(store, parts, "2", qs):
            return
        self._send_json(404, {"detail": "Not Found"})

    # ------------------------------------------------------------------
    # Main router
    # ------------------------------------------------------------------

    def _route(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query or "")

        # Health check (no auth)
        if path in ("/health", "/health/") and self.command == "GET":
            self._send_json(200, {"status": "ok"})
            return

        # API version discovery (no auth) — AAPModule.authenticate() probes this first
        # without an Authorization header to discover API versions before adding credentials.
        if self.command == "GET":
            _vparts = [p for p in path.split("/") if p]
            _is_gateway_root = len(_vparts) == 2 and _vparts[0] == "api" and _vparts[1] == "gateway"
            _is_versioned_root = len(_vparts) == 3 and _vparts[0] == "api" and _vparts[1] == "gateway" and _vparts[2].startswith("v")
            if _is_gateway_root or _is_versioned_root:
                v = self.reported_api_version
                self._send_json(
                    200,
                    {
                        "current_version": f"/api/gateway/v{v}/",
                        "available_versions": {"v1": "/api/gateway/v1/", "v2": "/api/gateway/v2/"},
                    },
                )
                return

        if not self._require_auth():
            self._send_json(401, {"detail": "Missing Authorization header"})
            return

        parts = [p for p in path.split("/") if p]

        if len(parts) >= 2 and parts[0] == "api" and parts[1] == "controller":
            self._route_controller(parts, qs)
            return

        if len(parts) < 3 or parts[0] != "api" or parts[1] != "gateway":
            self._send_json(404, {"detail": "Not Found"})
            return

        version_part = parts[2]
        if not version_part.startswith("v"):
            self._send_json(404, {"detail": "Not Found"})
            return
        version = version_part[1:]

        # /api/gateway/vX/ping/
        if len(parts) == 4 and parts[3] == "ping" and self.command == "GET":
            headers = {"X-API-Version": self.reported_api_version}
            self._send_json(200, {"version": self.reported_api_version}, headers=headers)
            return

        resource = parts[3] if len(parts) >= 4 else None

        # ---- Settings (special: singleton, no id-based CRUD) ----
        if resource == "settings":
            # /api/gateway/vX/settings/all/  — GET (flat dict) or PUT (full replace)
            if len(parts) == 5 and parts[4] == "all":
                if self.command == "GET":
                    self._send_json(200, self.store.get_settings_all())
                    return
                if self.command in ("PUT", "PATCH"):
                    # settings module uses PUT settings/all to update
                    payload = self._parse_json_body()
                    self._send_json(200, self.store.patch_settings(payload))
                    return
            # /api/gateway/vX/settings/
            if len(parts) == 4:
                if self.command == "GET":
                    self._send_json(200, self.store.get_settings_list())
                    return
                if self.command == "PATCH":
                    payload = self._parse_json_body()
                    self._send_json(200, self.store.patch_settings(payload))
                    return
            self._send_json(404, {"detail": "Not Found"})
            return

        # ---- Users ----
        if resource == "users":
            if len(parts) == 4:
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
            if len(parts) == 5:
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

        # ---- Organizations ----
        if resource == "organizations":
            if len(parts) == 4:
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
            if len(parts) == 5:
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

        # ---- Teams ----
        if resource == "teams":
            if len(parts) == 4:
                if self.command == "GET":
                    name = (qs.get("name") or [None])[0]
                    org_q = (qs.get("organization") or [None])[0]
                    org_id = int(org_q) if org_q and str(org_q).isdigit() else None
                    self._send_json(200, self.store.list_teams(name=name, organization=org_id))
                    return
                if self.command == "POST":
                    try:
                        payload = self._parse_json_body()
                        created = self.store.create_team(version=version, payload=payload)
                        self._send_json(201, created)
                    except ValueError as e:
                        self._send_json(400, {"detail": str(e)})
                    return
            if len(parts) == 5:
                try:
                    team_id = int(parts[4])
                except ValueError:
                    self._send_json(404, {"detail": "Not Found"})
                    return
                if self.command == "GET":
                    try:
                        self._send_json(200, self.store.get_team(team_id))
                    except KeyError:
                        self._send_json(404, {"detail": "Not Found"})
                    return
                if self.command == "PATCH":
                    try:
                        payload = self._parse_json_body()
                        self._send_json(200, self.store.patch_team(team_id, payload))
                    except KeyError:
                        self._send_json(404, {"detail": "Not Found"})
                    return
                if self.command == "DELETE":
                    try:
                        self.store.delete_team(team_id)
                        self._send_empty(204)
                    except KeyError:
                        self._send_json(404, {"detail": "Not Found"})
                    return

        # ---- All other resources — generic handler ----
        if resource in self.store._resources:
            if self._handle_generic_resource(resource, parts, version, qs):
                return

        self._send_json(404, {"detail": "Not Found"})

    def do_GET(self) -> None:  # noqa: N802
        self._route()

    def do_POST(self) -> None:  # noqa: N802
        self._route()

    def do_PATCH(self) -> None:  # noqa: N802
        self._route()

    def do_PUT(self) -> None:  # noqa: N802
        self._route()

    def do_DELETE(self) -> None:  # noqa: N802
        self._route()


# ---------------------------------------------------------------------------
# Server bootstrap
# ---------------------------------------------------------------------------


class MockGatewayServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, *, store: Store, reported_api_version: str):
        super().__init__(server_address, RequestHandlerClass)
        self.store = store
        self.reported_api_version = reported_api_version


def main() -> int:
    parser = argparse.ArgumentParser(description="Mock AAP Gateway API server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reported-api-version", default="1")
    parser.add_argument("--daemon", action="store_true", help="Fork and print child PID (for Molecule create/destroy).")
    args = parser.parse_args()

    store = Store()
    store._init_resources()
    store._init_controller_resources()
    store.seed_defaults()

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
            print(str(pid))
            return 0
        httpd.serve_forever()
        return 0

    resources = ", ".join(sorted(store._resources.keys()))
    print(f"Mock Gateway on http://{args.host}:{args.port} (api_version={args.reported_api_version})")
    print(f"Generic resources: {resources}")
    print("Legacy: users, organizations, teams | Special: settings, settings/all")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
