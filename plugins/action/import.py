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
    ("labels", "label"),
    ("inventory", "inventory"),
    ("inventory_sources", "inventory_source"),
    ("job_templates", "job_template"),
    ("workflow_job_templates", "workflow_job_template"),
    ("schedules", "schedule"),
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

# Fields that are inline children, not direct module params — popped and handled separately.
INLINE_CHILDREN_FIELDS = frozenset({"hosts", "groups"})
IMPORT_CONTROL_FIELDS = frozenset({"state"})


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

            any_changed = False
            results_summary = {}
            failed_resources = []

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

                for index, resource_data in enumerate(resource_list):
                    if not isinstance(resource_data, dict):
                        type_result["failed"] += 1
                        failed_resources.append({"type": export_key, "name": "[%d]" % index, "error": "Expected a resource dictionary."})
                        continue

                    clean_data = {
                        k: v for k, v in resource_data.items() if k not in STRIP_FIELDS and k not in INLINE_CHILDREN_FIELDS and k not in IMPORT_CONTROL_FIELDS
                    }
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
            import traceback as _tb

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
