#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.import.

Imports resources in dependency order through their resource action plugins,
sharing one manager connection so resource-specific transformations and
association handling are preserved.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import traceback as _tb

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.filter.controller_export import from_awxkit_export
from ansible_collections.ansible.platform.plugins.plugin_utils.resource_type_map import (
    ASSIGNMENT_TYPE_PATH_MAP,
    CONTROLLER_NON_ORG_TYPES,
    service_kind,
)

# Dependency-ordered list of (export_key, module_name) tuples.
# Resources earlier in the list have no FK dependencies on later ones.
IMPORT_ORDER = [
    ("organizations", "organization"),
    ("authenticators", "authenticator"),
    ("authenticator_maps", "authenticator_map"),
    ("users", "user"),
    ("teams", "team"),
    ("role_definitions", "role_definition"),
    ("credential_types", "controller_credential_type"),
    ("credentials", "controller_credential"),
    ("execution_environments", "execution_environment"),
    ("instance_groups", "instance_group"),
    ("notification_templates", "notification_template"),
    ("projects", "controller_project"),
    ("labels", "label"),
    ("inventory", "inventory"),
    ("inventory_sources", "inventory_source"),
    ("job_templates", "job_template"),
    ("workflow_job_templates", "workflow_job_template"),
    ("schedules", "schedule"),
    # Controller organization overlays depend on organizations, credentials,
    # and instance groups, so apply them after those base resources exist.
    ("controller_organizations", "organization"),
    ("role_user_assignments", "role_user_assignment"),
    ("role_team_assignments", "role_team_assignment"),
]

# Fields from legacy/API data that are not module parameters.
STRIP_FIELDS = frozenset(
    {
        "id",
        "type",
        "url",
        "related",
        "summary_fields",
        "created",
        "modified",
        "natural_key",
        "managed",
        "user_capabilities",
        "object_roles",
        # API response fields that are not resource-module inputs.
        "organization_ids",
        "scm_revision",
    }
)

# ``type`` is API metadata for most resources, but it is a required input for
# authenticator resources and must survive the import cleanup step.
RESOURCE_FIELDS_TO_PRESERVE = {
    "authenticators": frozenset({"type"}),
}

# Fields that are inline children, not direct module params — popped and handled separately.
INLINE_CHILDREN_FIELDS = frozenset({"hosts", "groups"})
IMPORT_CONTROL_FIELDS = frozenset({"state"})

_ROLE_ASSIGNMENT_TYPES = frozenset({"role_user_assignments", "role_team_assignments"})
_ROLE_CACHE_MAX_OBJECTS = 10000


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "import"

    def run(self, tmp=None, task_vars=None):
        """Import resources in dependency order using one manager connection."""
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            assets = validated_params.get("assets")
            if not assets or not isinstance(assets, dict):
                result["changed"] = False
                result["failed"] = True
                result["msg"] = "The 'assets' parameter must be a non-empty dict."
                return result

            if validated_params.get("auto_convert_legacy", False):
                assets = from_awxkit_export(assets)

            task_vars = task_vars or {}

            check_mode = self._play_context.check_mode
            # Token values are write-only and token creation is intentionally
            # non-idempotent. Keep exported token metadata visible, but never
            # recreate tokens implicitly during a full import.
            results_summary = {}
            if isinstance(assets.get("tokens"), list):
                results_summary["tokens"] = {
                    "changed": 0,
                    "ok": len(assets["tokens"]),
                    "failed": 0,
                    "skipped": len(assets["tokens"]),
                    "reason": "token values are write-only; issue tokens explicitly",
                }

            any_changed = False
            failed_resources = []
            _role_cache = None

            for export_key, module_name in IMPORT_ORDER:
                if export_key not in assets:
                    continue

                resource_list = assets[export_key]
                type_result = {"changed": 0, "ok": 0, "failed": 0}
                results_summary[export_key] = type_result

                if not isinstance(resource_list, list):
                    type_result["failed"] = 1
                    failed_resources.append({"type": export_key, "name": "<collection>", "error": "Expected a list of resource dictionaries."})
                    continue

                if export_key in _ROLE_ASSIGNMENT_TYPES and _role_cache is None:
                    _role_cache = self._build_role_assignment_cache(manager, assets)

                for index, resource_data in enumerate(resource_list):
                    if not isinstance(resource_data, dict):
                        type_result["failed"] += 1
                        failed_resources.append({"type": export_key, "name": "[%d]" % index, "error": "Expected a resource dictionary."})
                        continue

                    clean_data = {
                        k: v
                        for k, v in resource_data.items()
                        if (k not in STRIP_FIELDS or k in RESOURCE_FIELDS_TO_PRESERVE.get(export_key, frozenset()))
                        and k not in INLINE_CHILDREN_FIELDS
                        and k not in IMPORT_CONTROL_FIELDS
                    }
                    if export_key in _ROLE_ASSIGNMENT_TYPES and _role_cache is not None:
                        clean_data = self._pre_resolve_role_assignment(clean_data, _role_cache, export_key)
                    resource_name = clean_data.get("name") or clean_data.get("username") or clean_data.get("hostname") or "unknown"
                    try:
                        changed = self._import_single_resource(manager, module_name, clean_data, task_vars)
                        if changed:
                            type_result["changed"] += 1
                            any_changed = True
                        else:
                            type_result["ok"] += 1
                    except Exception as exc:
                        type_result["failed"] += 1
                        failed_resources.append({"type": export_key, "name": resource_name, "error": str(exc)})
                        self._display.warning("Failed to import %s '%s': %s" % (module_name, resource_name, exc))

            # Import hosts and groups nested under inventories
            inventory_list = assets.get("inventory", [])
            if isinstance(inventory_list, list):
                host_results, group_results = self._import_inventory_children(manager, inventory_list, check_mode, failed_resources, task_vars)
                if host_results["changed"] or host_results["ok"] or host_results["failed"]:
                    results_summary["hosts"] = host_results
                    if host_results["changed"]:
                        any_changed = True
                if group_results["changed"] or group_results["ok"] or group_results["failed"]:
                    results_summary["groups"] = group_results
                    if group_results["changed"]:
                        any_changed = True

            result["changed"] = any_changed
            result["failed"] = bool(failed_resources)
            result["results"] = results_summary
            if failed_resources:
                result["failed_resources"] = failed_resources
                result["msg"] = "%d resource(s) failed to import." % len(failed_resources)

        except Exception as exc:
            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result

    def _run_resource_action(self, manager, module_name, resource_data, task_vars):
        """Run the resource action plugin with this import's shared manager."""
        resource_task = self._task.copy()
        resource_task.action = "ansible.platform.%s" % module_name
        resource_task.args = dict(resource_data)
        resource_action = self._shared_loader_obj.action_loader.get(
            resource_task.action,
            resource_task,
            self._connection,
            self._play_context,
            self._loader,
            self._templar,
            self._shared_loader_obj,
        )
        resource_action._manager_override = manager
        resource_action._explicit_fields_to_send = frozenset(resource_data)
        resource_action._preserve_explicit_nulls_for_update = True
        action_result = resource_action.run(task_vars=task_vars)

        if not isinstance(action_result, dict):
            raise ValueError("Action plugin for %s returned an invalid result" % module_name)
        if action_result.get("failed"):
            raise ValueError(action_result.get("msg") or "Action plugin for %s failed" % module_name)
        if "changed" not in action_result:
            raise ValueError("Action plugin for %s did not return an explicit changed flag" % module_name)
        return action_result

    def _import_single_resource(self, manager, module_name, resource_data, task_vars):
        """Import one resource through its action plugin and return changed."""
        return bool(self._run_resource_action(manager, module_name, resource_data, task_vars)["changed"])

    def _build_role_assignment_cache(self, manager, assets):
        """Pre-fetch target resources so role-assignment FK resolution needs no per-item API calls."""
        cache = {}
        max_objects = _ROLE_CACHE_MAX_OBJECTS

        def _fetch_name_map(endpoint, id_field="name"):
            response = manager.search_api(endpoint=endpoint, return_all=True, max_objects=max_objects)
            return {r[id_field]: r["id"] for r in response.get("results", []) if isinstance(r, dict) and id_field in r and "id" in r}

        self._display.vvv("Building role-assignment resolution cache...")
        cache["role_definitions"] = _fetch_name_map("api/gateway/v1/role_definitions/")
        user_names = set()
        for key in _ROLE_ASSIGNMENT_TYPES:
            for item in assets.get(key, []):
                if isinstance(item, dict):
                    user = item.get("user")
                    if isinstance(user, str) and not user.isdigit():
                        user_names.add(user)
        cache["users"] = {}
        for username in user_names:
            response = manager.search_api(
                endpoint="api/gateway/v1/users/",
                query_params={"username": username},
                return_all=True,
                max_objects=max_objects,
            )
            for user in response.get("results", []):
                if user.get("username") == username and user.get("id") is not None:
                    cache["users"][username] = user["id"]
        cache["gateway_orgs"] = _fetch_name_map("api/gateway/v1/organizations/")
        cache["controller_orgs"] = _fetch_name_map("api/controller/v2/organizations/")

        response = manager.search_api(endpoint="api/gateway/v1/teams/", return_all=True, max_objects=max_objects)
        teams_scoped = {}
        teams_unscoped = {}
        for t in response.get("results", []):
            if "name" not in t or "id" not in t:
                continue
            teams_scoped[(t["name"], t.get("organization"))] = t["id"]
            if t["name"] not in teams_unscoped:
                teams_unscoped[t["name"]] = t["id"]
            else:
                teams_unscoped[t["name"]] = None
        cache["teams"] = teams_scoped
        cache["teams_unscoped"] = teams_unscoped

        object_types = set()
        for key in _ROLE_ASSIGNMENT_TYPES:
            for item in assets.get(key, []):
                if not isinstance(item, dict):
                    continue
                if item.get("object_type"):
                    object_types.add(item["object_type"])
                for ao in item.get("assignment_objects", []):
                    if isinstance(ao, dict) and ao.get("type"):
                        object_types.add(ao["type"])

        for obj_type in object_types:
            if obj_type in ("organizations", "teams"):
                continue
            path = ASSIGNMENT_TYPE_PATH_MAP.get(obj_type)
            # Import/export currently supports Gateway and Controller RBAC
            # objects only. Do not prefetch EDA or Hub resources here.
            if not path or service_kind(obj_type) != "controller":
                continue
            try:
                response = manager.search_api(endpoint=path, return_all=True, max_objects=max_objects)
            except Exception as exc:
                self._display.vvv("Role-assignment cache: skipping %s: %s" % (obj_type, exc))
                continue
            scoped = {}
            unscoped = {}
            credential_types = _fetch_name_map("api/controller/v2/credential_types/") if obj_type == "awx.credential" else {}
            for r in response.get("results", []):
                if "name" not in r or "id" not in r:
                    continue
                credential_type = None
                if obj_type == "awx.credential":
                    credential_type = credential_types.get(r.get("credential_type"), r.get("credential_type"))
                scoped_key = (r["name"], r.get("organization"), credential_type) if obj_type == "awx.credential" else (r["name"], r.get("organization"))
                scoped[scoped_key] = r["id"]
                unscoped_key = (r["name"], credential_type) if obj_type == "awx.credential" else r["name"]
                if unscoped_key not in unscoped:
                    unscoped[unscoped_key] = r["id"]
                else:
                    unscoped[unscoped_key] = None
            cache[obj_type] = scoped
            cache[obj_type + ":unscoped"] = unscoped

        self._display.vvv(
            "Role-assignment cache ready: %d role definitions, %d users, %d teams"
            % (
                len(cache.get("role_definitions", {})),
                len(cache.get("users", {})),
                len(teams_scoped),
            )
        )
        return cache

    def _resolve_object_from_cache(self, cache, obj_type, obj_name, org_name, credential_type=None):
        """Resolve an object name + type + org to a target-instance ID from the pre-built cache."""
        if obj_type == "organizations":
            return cache.get("gateway_orgs", {}).get(obj_name)

        if obj_type == "teams":
            if org_name:
                org_id = cache.get("gateway_orgs", {}).get(org_name)
                if org_id is not None:
                    return cache.get("teams", {}).get((obj_name, org_id))
                # Org explicitly provided but not found on target — do not
                # fall back to an unscoped match from a different org.
                return None
            return cache.get("teams_unscoped", {}).get(obj_name)

        scoped = cache.get(obj_type, {})
        unscoped = cache.get(obj_type + ":unscoped", {})
        key_suffix = credential_type if obj_type == "awx.credential" else None

        if org_name and obj_type not in CONTROLLER_NON_ORG_TYPES:
            org_id = cache.get("controller_orgs", {}).get(org_name)
            if org_id is not None:
                return scoped.get((obj_name, org_id, key_suffix)) if obj_type == "awx.credential" else scoped.get((obj_name, org_id))
            # Org explicitly provided but not found on target — do not
            # fall back to an unscoped match from a different org.
            return None

        return unscoped.get((obj_name, key_suffix)) if obj_type == "awx.credential" else unscoped.get(obj_name)

    def _pre_resolve_role_assignment(self, clean_data, cache, export_key):
        """Replace portable names with target-instance integer IDs for one role assignment."""
        resolved = dict(clean_data)

        rd = resolved.get("role_definition")
        if isinstance(rd, str):
            rd_id = cache.get("role_definitions", {}).get(rd)
            if rd_id is not None:
                resolved["role_definition"] = rd_id

        if export_key == "role_user_assignments":
            user = resolved.get("user")
            if isinstance(user, str):
                if user.isdigit():
                    resolved["user"] = int(user)
                else:
                    user_id = cache.get("users", {}).get(user)
                    if user_id is not None:
                        resolved["user"] = user_id

        if export_key == "role_team_assignments":
            team = resolved.get("team")
            if isinstance(team, str):
                team_org = resolved.get("team_organization")
                if team_org:
                    org_id = cache.get("gateway_orgs", {}).get(team_org)
                    if org_id is not None:
                        team_id = cache.get("teams", {}).get((team, org_id))
                        if team_id is not None:
                            resolved["team"] = team_id
                            resolved.pop("team_organization", None)
                else:
                    team_id = cache.get("teams_unscoped", {}).get(team)
                    if team_id is not None:
                        resolved["team"] = team_id

        obj_name = resolved.get("object_name")
        obj_type = resolved.get("object_type")
        if obj_name and obj_type:
            org_name = resolved.get("organization")
            obj_id = self._resolve_object_from_cache(cache, obj_type, obj_name, org_name, resolved.get("object_credential_type"))
            if obj_id is not None:
                resolved["object_id"] = obj_id
                del resolved["object_name"]
                del resolved["object_type"]
                resolved.pop("organization", None)
                resolved.pop("object_credential_type", None)

        if isinstance(resolved.get("assignment_objects"), list):
            pre_resolved = []
            for ao in resolved["assignment_objects"]:
                if isinstance(ao, dict) and ao.get("name") and ao.get("type"):
                    ao_id = self._resolve_object_from_cache(cache, ao["type"], ao["name"], ao.get("organization"), ao.get("credential_type"))
                    if ao_id is not None:
                        pre_resolved.append({"object_id": ao_id})
                        continue
                pre_resolved.append(ao)
            resolved["assignment_objects"] = pre_resolved

        return resolved

    def _import_inventory_children(self, manager, inventory_list, check_mode, failed_resources, task_vars):
        """Import hosts and groups nested under inventory entries."""
        host_results = {"changed": 0, "ok": 0, "failed": 0}
        group_results = {"changed": 0, "ok": 0, "failed": 0}

        for inv in inventory_list:
            if not isinstance(inv, dict):
                continue
            inv_name = inv.get("name", "unknown")

            for index, host in enumerate(inv.get("hosts", [])):
                if not isinstance(host, dict):
                    host_results["failed"] += 1
                    failed_resources.append({"type": "hosts", "name": "[%d]" % index, "error": "Expected a resource dictionary."})
                    continue
                host_data = {k: v for k, v in host.items() if k not in STRIP_FIELDS and k not in IMPORT_CONTROL_FIELDS and v is not None}
                host_data["inventory"] = inv_name
                host_name = host_data.get("name") or host_data.get("hostname") or "unknown"

                try:
                    changed = self._import_single_resource(manager, "host", host_data, task_vars)
                    if changed:
                        host_results["changed"] += 1
                    else:
                        host_results["ok"] += 1
                except Exception as exc:
                    host_results["failed"] += 1
                    failed_resources.append({"type": "hosts", "name": host_name, "error": str(exc)})

            group_records = []
            for index, group in enumerate(inv.get("groups", [])):
                if not isinstance(group, dict):
                    group_results["failed"] += 1
                    failed_resources.append({"type": "groups", "name": "[%d]" % index, "error": "Expected a resource dictionary."})
                    continue
                group_data = {
                    k: v
                    for k, v in group.items()
                    if k not in STRIP_FIELDS and k not in INLINE_CHILDREN_FIELDS and k not in IMPORT_CONTROL_FIELDS and v is not None
                }
                group_data["inventory"] = inv_name
                group_name = group_data.get("name", "unknown")

                try:
                    group_result = self._run_resource_action(manager, "group", group_data, task_vars)
                    group_id = group_result.get("id") or (group_result.get("group") or {}).get("id")
                    changed = bool(group_result["changed"])
                    group_records.append((group_data, group, changed, group_id))
                except Exception as exc:
                    group_results["failed"] += 1
                    failed_resources.append({"type": "groups", "name": group_name, "error": str(exc)})

            # All groups must exist before child-group relationships are resolved.
            for group_data, group, changed, group_id in group_records:
                association_changed = False
                if group.get("hosts") is not None or group.get("children") is not None:
                    try:
                        if not group_id and not check_mode:
                            raise ValueError("Imported group '%s' could not be found for association import" % group_data.get("name", "unknown"))
                        if check_mode:
                            association_changed = True
                        else:
                            if group.get("hosts") is not None:
                                association_changed |= manager.manage_associations(
                                    "groups", group_id, "hosts", group["hosts"], "hosts", "name", service="controller"
                                )
                            if group.get("children") is not None:
                                association_changed |= manager.manage_associations(
                                    "groups", group_id, "children", group["children"], "groups", "name", service="controller"
                                )
                    except Exception as exc:
                        group_results["failed"] += 1
                        failed_resources.append({"type": "groups", "name": group_data.get("name", "unknown"), "error": str(exc)})
                        continue

                if changed or association_changed:
                    group_results["changed"] += 1
                else:
                    group_results["ok"] += 1

        return host_results, group_results
