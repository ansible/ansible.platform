#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.import.

Thin wrapper that imports resources by calling manager.execute() for each
resource in dependency order. Uses one manager connection for all operations.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.filter.controller_export import from_awxkit_export

# Dependency-ordered list of (export_key, module_name) tuples.
# Resources earlier in the list have no FK dependencies on later ones.
IMPORT_ORDER = [
    ("organizations", "organization"),
    ("users", "user"),
    ("teams", "team"),
    ("credential_types", "controller_credential_type"),
    ("credentials", "controller_credential"),
    ("execution_environments", "execution_environment"),
    ("notification_templates", "notification_template"),
    ("projects", "controller_project"),
    ("inventory", "inventory"),
    ("inventory_sources", "inventory_source"),
    ("job_templates", "job_template"),
    ("workflow_job_templates", "workflow_job_template"),
    ("schedules", "schedule"),
]

# Fields from legacy/API data that are not module parameters.
STRIP_FIELDS = frozenset({
    "id", "type", "url", "related", "summary_fields", "created", "modified",
    "natural_key", "managed", "user_capabilities", "object_roles",
})

# Fields that are inline children, not direct module params — popped and handled separately.
INLINE_CHILDREN_FIELDS = frozenset({"hosts", "groups"})


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

            check_mode = self._play_context.check_mode

            any_changed = False
            results_summary = {}
            failed_resources = []

            for export_key, module_name in IMPORT_ORDER:
                resource_list = assets.get(export_key)
                if not resource_list or not isinstance(resource_list, list):
                    continue

                type_result = {"changed": 0, "ok": 0, "failed": 0}

                for resource_data in resource_list:
                    if not isinstance(resource_data, dict):
                        continue

                    clean_data = {k: v for k, v in resource_data.items() if k not in STRIP_FIELDS and k not in INLINE_CHILDREN_FIELDS and v is not None}
                    resource_name = clean_data.get("name") or clean_data.get("username") or clean_data.get("hostname") or "unknown"

                    if check_mode:
                        type_result["changed"] += 1
                        any_changed = True
                        continue

                    try:
                        changed = self._import_single_resource(manager, module_name, clean_data)
                        if changed:
                            type_result["changed"] += 1
                            any_changed = True
                        else:
                            type_result["ok"] += 1
                    except Exception as exc:
                        type_result["failed"] += 1
                        failed_resources.append({"type": export_key, "name": resource_name, "error": str(exc)})
                        self._display.warning("Failed to import %s '%s': %s" % (module_name, resource_name, exc))

                results_summary[export_key] = type_result

            # Import hosts and groups nested under inventories
            inventory_list = assets.get("inventory", [])
            if isinstance(inventory_list, list):
                host_results, group_results = self._import_inventory_children(manager, inventory_list, check_mode, failed_resources)
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
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result

    def _import_single_resource(self, manager, module_name, resource_data):
        """Import one resource: find → update if exists, create if not.

        Returns True if the resource was changed (created or updated).
        """
        try:
            existing = manager.execute(
                operation="find",
                module_name=module_name,
                ansible_data=dict(resource_data),
            )
        except (ValueError, Exception):
            existing = None

        if existing and existing.get("id"):
            update_data = dict(resource_data)
            update_data["id"] = existing["id"]
            manager.execute(
                operation="update",
                module_name=module_name,
                ansible_data=update_data,
            )
            return True
        else:
            manager.execute(
                operation="create",
                module_name=module_name,
                ansible_data=dict(resource_data),
            )
            return True

    def _import_inventory_children(self, manager, inventory_list, check_mode, failed_resources):
        """Import hosts and groups nested under inventory entries."""
        host_results = {"changed": 0, "ok": 0, "failed": 0}
        group_results = {"changed": 0, "ok": 0, "failed": 0}

        for inv in inventory_list:
            if not isinstance(inv, dict):
                continue
            inv_name = inv.get("name", "unknown")

            for host in inv.get("hosts", []):
                if not isinstance(host, dict):
                    continue
                host_data = {k: v for k, v in host.items() if k not in STRIP_FIELDS and v is not None}
                host_data["inventory"] = inv_name
                host_name = host_data.get("name") or host_data.get("hostname") or "unknown"

                if check_mode:
                    host_results["changed"] += 1
                    continue

                try:
                    changed = self._import_single_resource(manager, "host", host_data)
                    if changed:
                        host_results["changed"] += 1
                    else:
                        host_results["ok"] += 1
                except Exception as exc:
                    host_results["failed"] += 1
                    failed_resources.append({"type": "hosts", "name": host_name, "error": str(exc)})

            for group in inv.get("groups", []):
                if not isinstance(group, dict):
                    continue
                group_data = {k: v for k, v in group.items() if k not in STRIP_FIELDS and v is not None}
                group_data["inventory"] = inv_name
                group_name = group_data.get("name", "unknown")

                if check_mode:
                    group_results["changed"] += 1
                    continue

                try:
                    changed = self._import_single_resource(manager, "group", group_data)
                    if changed:
                        group_results["changed"] += 1
                    else:
                        group_results["ok"] += 1
                except Exception as exc:
                    group_results["failed"] += 1
                    failed_resources.append({"type": "groups", "name": group_name, "error": str(exc)})

        return host_results, group_results
