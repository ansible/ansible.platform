#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.workflow_job_template import (
    AnsibleWorkflowJobTemplate,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.workflow_job_template import BASE_PATH
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.workflow_job_template_node import (
    BASE_PATH as NODE_BASE_PATH,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import ResourceNotFoundError

_ASSOC_MAP = {
    "labels": ("labels", "name"),
    "notification_templates_started": ("notification_templates", "name"),
    "notification_templates_success": ("notification_templates", "name"),
    "notification_templates_error": ("notification_templates", "name"),
    "notification_templates_approvals": ("notification_templates", "name"),
}

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "workflow_job_template"
    MODEL_CLASS = AnsibleWorkflowJobTemplate
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset(
        {
            "copy_from",
            "survey_spec",
            "workflow_nodes",
            "destroy_current_nodes",
        }
        | set(_ASSOC_MAP)
    )

    def _build_argspec_from_docs(self, documentation):
        argspec = super()._build_argspec_from_docs(documentation)
        wn = argspec["argument_spec"].get("workflow_nodes")
        if wn and "suboptions" in wn:
            wn["options"] = wn.pop("suboptions")
        return argspec

    def _should_update(self, desired_data, current_data):
        desired = dict(desired_data)
        desired.pop("organization", None)
        for field, endpoint in (
            ("inventory", "inventories"),
            ("webhook_credential", "credentials"),
        ):
            value = desired.get(field)
            if value is not None and str(value).isdigit() and current_data.get(field) is not None:
                resource = self._client.search_api(f"{BASE_PATH.rsplit('/', 1)[0]}/{endpoint}/{value}/")
                desired[field] = resource.get("name", value)
        return super()._should_update(desired, current_data)

    # ── Graph management helpers ──

    def _destroy_workflow_nodes(self, manager, workflow_id, check_mode):
        """Delete all existing workflow nodes for a workflow."""
        node_path = f"{NODE_BASE_PATH}/"
        existing = manager.search_api(
            node_path,
            query_params={"workflow_job_template": workflow_id},
            return_all=True,
            max_objects=100000,
        )
        nodes = existing.get("results", [])
        if not nodes:
            return False
        if not check_mode:
            for node in nodes:
                manager.direct_request("DELETE", f"{node_path}{node['id']}/")
        return True

    @staticmethod
    def _resolve_ujt_id(manager, ujt_data):
        """Resolve a unified_job_template dict to an API ID."""
        if not ujt_data or not ujt_data.get("name"):
            return None

        name = ujt_data["name"]
        ujt_type = ujt_data.get("type")

        if ujt_type == "workflow_approval":
            return None

        extra = {}
        if ujt_type:
            extra["type"] = ujt_type

        if ujt_type == "inventory_source":
            inv = ujt_data.get("inventory", {})
            org_data = inv.get("organization") if isinstance(inv, dict) else None
        else:
            org_data = ujt_data.get("organization")

        if isinstance(org_data, dict) and org_data.get("name"):
            extra["organization"] = manager.lookup_resource_id("organizations", "name", org_data["name"], service=_SERVICE)

        return manager.lookup_resource_id(
            "unified_job_templates",
            "name",
            name,
            service=_SERVICE,
            extra_query_params=extra or None,
        )

    @staticmethod
    def _resolve_inventory_id(manager, inv_data):
        """Resolve an inventory reference (string or dict) to an ID."""
        if inv_data is None:
            return None
        if isinstance(inv_data, dict):
            name = inv_data.get("name")
            if not name:
                return None
            extra = {}
            org = inv_data.get("organization")
            if isinstance(org, dict) and org.get("name"):
                extra["organization"] = manager.lookup_resource_id("organizations", "name", org["name"], service=_SERVICE)
            return manager.lookup_resource_id("inventories", "name", name, service=_SERVICE, extra_query_params=extra or None)
        return manager.lookup_resource_id("inventories", "name", str(inv_data), service=_SERVICE)

    @staticmethod
    def _resolve_ee_id(manager, ee_data):
        """Resolve an execution_environment reference (string or dict) to an ID."""
        if ee_data is None:
            return None
        name = ee_data.get("name") if isinstance(ee_data, dict) else str(ee_data)
        if not name:
            return None
        return manager.lookup_resource_id("execution_environments", "name", name, service=_SERVICE)

    def _find_node_in_workflow(self, manager, identifier, workflow_id):
        """Look up a single node by identifier within a workflow."""
        result = manager.search_api(
            f"{NODE_BASE_PATH}/",
            query_params={"identifier": identifier, "workflow_job_template": workflow_id},
        )
        for item in result.get("results", []):
            if item.get("identifier") == identifier:
                return item
        return None

    def _manage_workflow_nodes(self, manager, workflow_id, workflow_nodes, check_mode):
        """Create, update, or delete workflow nodes from a declarative list."""
        node_path = f"{NODE_BASE_PATH}/"
        changed = False

        for node_spec in workflow_nodes:
            identifier = node_spec.get("identifier")
            if not identifier:
                raise ValueError("Each workflow node must have an 'identifier'")

            node_state = node_spec.get("state", "present")
            existing_node = self._find_node_in_workflow(manager, identifier, workflow_id)

            if node_state == "absent":
                if existing_node:
                    if not check_mode:
                        manager.direct_request("DELETE", f"{node_path}{existing_node['id']}/")
                    changed = True
                continue

            node_fields = {
                "identifier": identifier,
                "workflow_job_template": workflow_id,
            }

            ujt_data = node_spec.get("unified_job_template")
            if not ujt_data:
                raise ValueError("Workflow node '%s' requires 'unified_job_template'" % identifier)
            if not ujt_data.get("name"):
                raise ValueError("Workflow node '%s' requires 'name' in 'unified_job_template'" % identifier)
            if ujt_data.get("type") == "workflow_approval":
                existing_ujt_id = existing_node.get("unified_job_template") if existing_node else None
                if existing_ujt_id is not None:
                    try:
                        tmpl = manager.search_api(f"/api/controller/v2/workflow_approval_templates/{existing_ujt_id}/")
                        is_approval = tmpl.get("type") == "workflow_approval_template"
                    except Exception:
                        is_approval = False
                    if not is_approval:
                        node_fields["unified_job_template"] = None
            else:
                if not ujt_data.get("type"):
                    raise ValueError("Workflow node '%s' requires 'type' in 'unified_job_template'" % identifier)
                ujt_id = self._resolve_ujt_id(manager, ujt_data)
                if ujt_id is not None:
                    node_fields["unified_job_template"] = ujt_id

            inv_id = self._resolve_inventory_id(manager, node_spec.get("inventory"))
            if inv_id is not None:
                node_fields["inventory"] = inv_id

            ee_id = self._resolve_ee_id(manager, node_spec.get("execution_environment"))
            if ee_id is not None:
                node_fields["execution_environment"] = ee_id

            for scalar in (
                "extra_data",
                "scm_branch",
                "job_type",
                "job_tags",
                "skip_tags",
                "limit",
                "diff_mode",
                "verbosity",
                "forks",
                "job_slice_count",
                "timeout",
                "all_parents_must_converge",
            ):
                val = node_spec.get(scalar)
                if val is not None:
                    node_fields[scalar] = val

            if existing_node:
                needs_update = any(existing_node.get(k) != v for k, v in node_fields.items() if k not in ("identifier", "workflow_job_template"))
                if needs_update:
                    if not check_mode:
                        manager.direct_request("PATCH", f"{node_path}{existing_node['id']}/", node_fields)
                    changed = True
            else:
                if not check_mode:
                    manager.post_resource(node_path, node_fields, service=_SERVICE)
                changed = True

            if ujt_data and ujt_data.get("type") == "workflow_approval":
                approval_data = {k: ujt_data[k] for k in ("name", "description", "timeout") if ujt_data.get(k) is not None}
                if approval_data:
                    if check_mode:
                        changed = True
                    else:
                        node = self._find_node_in_workflow(manager, identifier, workflow_id)
                        if node and manager.manage_workflow_approval(node["id"], approval_data, check_mode=False):
                            changed = True

        return changed

    def _validate_workflow_nodes(self, manager, workflow_nodes):
        """Pre-validate all workflow node specs before any graph mutation."""
        for node_spec in workflow_nodes:
            identifier = node_spec.get("identifier")
            if not identifier:
                raise ValueError("Each workflow node must have an 'identifier'")
            if node_spec.get("state") == "absent":
                continue
            ujt_data = node_spec.get("unified_job_template")
            if not ujt_data:
                raise ValueError("Workflow node '%s' requires 'unified_job_template'" % identifier)
            if not ujt_data.get("name"):
                raise ValueError("Workflow node '%s' requires 'name' in 'unified_job_template'" % identifier)
            if ujt_data.get("type") != "workflow_approval":
                if not ujt_data.get("type"):
                    raise ValueError("Workflow node '%s' requires 'type' in 'unified_job_template'" % identifier)
                self._resolve_ujt_id(manager, ujt_data)

    def _manage_workflow_node_associations(self, manager, workflow_id, workflow_nodes, check_mode):
        """Wire up node-to-node and node-to-resource associations."""
        changed = False

        for node_spec in workflow_nodes:
            if node_spec.get("state") == "absent":
                continue

            identifier = node_spec.get("identifier")
            related = node_spec.get("related")
            if not related:
                continue

            node = self._find_node_in_workflow(manager, identifier, workflow_id)
            if not node:
                if check_mode:
                    changed = True
                    continue
                raise ValueError(f"Could not find workflow node '{identifier}' after creation")

            node_id = node["id"]

            for assoc_type in ("success_nodes", "failure_nodes", "always_nodes"):
                assoc_list = related.get(assoc_type)
                if assoc_list is None:
                    continue

                target_ids = []
                for entry in assoc_list:
                    target_ident = entry.get("identifier") if isinstance(entry, dict) else str(entry)
                    if not target_ident:
                        continue
                    target = self._find_node_in_workflow(manager, target_ident, workflow_id)
                    if target:
                        target_ids.append(target["id"])
                    elif check_mode:
                        changed = True
                    else:
                        raise ValueError(f"Could not find workflow node '{target_ident}' for {assoc_type}")

                if manager.manage_associations(
                    NODE_BASE_PATH,
                    node_id,
                    assoc_type,
                    target_ids,
                    "workflow_job_template_nodes",
                    "identifier",
                    service=_SERVICE,
                    check_mode=check_mode,
                ):
                    changed = True

            for assoc_type in ("credentials", "labels", "instance_groups"):
                assoc_list = related.get(assoc_type)
                if assoc_list is None:
                    continue

                desired = []
                for entry in assoc_list:
                    if isinstance(entry, dict) and entry.get("organization"):
                        org = entry["organization"]
                        org_name = org.get("name") if isinstance(org, dict) else str(org)
                        org_id = manager.lookup_resource_id("organizations", "name", org_name, service=_SERVICE)
                        rid = manager.lookup_resource_id(
                            assoc_type,
                            "name",
                            entry.get("name", ""),
                            service=_SERVICE,
                            extra_query_params={"organization": org_id},
                        )
                        desired.append(rid)
                    elif isinstance(entry, dict):
                        desired.append(entry.get("name", ""))
                    else:
                        desired.append(str(entry))

                if manager.manage_associations(
                    NODE_BASE_PATH,
                    node_id,
                    assoc_type,
                    desired,
                    assoc_type,
                    "name",
                    service=_SERVICE,
                    check_mode=check_mode,
                ):
                    changed = True

        return changed

    # ── Main entry point ──

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        copy_from = self._task.args.get("copy_from")
        if (survey_spec := self._task.args.get("survey_spec")) is None:
            survey_spec = self._task.args.get("survey")
        association_data = {field: self._task.args.get(field) for field in _ASSOC_MAP}

        workflow_nodes = self._task.args.get("workflow_nodes")
        if workflow_nodes is None:
            workflow_nodes = self._task.args.get("schema")
        destroy_current_nodes = self._task.args.get("destroy_current_nodes")
        if destroy_current_nodes is None:
            destroy_current_nodes = self._task.args.get("destroy_current_schema")
        if isinstance(destroy_current_nodes, str):
            destroy_current_nodes = destroy_current_nodes.lower() in ("true", "yes", "1")
        else:
            destroy_current_nodes = bool(destroy_current_nodes) if destroy_current_nodes is not None else False

        name = self._task.args.get("name")
        state = self._task.args.get("state", "present")
        check_mode = self._task.check_mode

        copied = False
        if copy_from and state not in ("absent", "exists") and not check_mode:
            try:
                self._validate_action_input()
            except Exception as exc:
                return {"changed": False, "failed": True, "msg": str(exc)}
            try:
                super(BaseResourceActionPlugin, self).run(tmp, task_vars)
                self._task_vars = task_vars
                manager, facts_to_set = self._get_or_spawn_manager(task_vars)
                self._client = manager
                existing = manager.search_api(BASE_PATH, query_params={"name": name})
                if not any(item.get("name") == name for item in existing.get("results", [])):
                    manager.copy_resource(self.MODULE_NAME, copy_from, name, BASE_PATH, service=_SERVICE)
                    copied = True
            except Exception as exc:
                return {"changed": False, "failed": True, "msg": "Failed to copy from '%s': %s" % (copy_from, exc)}

        result = super().run(tmp, task_vars)
        if copy_from:
            result["copied"] = copied
        if copied:
            result["changed"] = True
        if result.get("failed") or state in ("absent", "exists"):
            return result

        wjt_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")
        if not wjt_id:
            return result

        try:
            manager = self._client
            changed = False
            org_id = result.get("organization") or (result.get(self.MODULE_NAME) or {}).get("organization")
            for field, (lookup_endpoint, lookup_field) in _ASSOC_MAP.items():
                desired = association_data.get(field)
                if desired is None:
                    continue
                extra = {"organization": org_id} if field == "labels" and org_id is not None else None
                try:
                    association_changed = manager.manage_associations(
                        BASE_PATH,
                        wjt_id,
                        field,
                        desired,
                        lookup_endpoint,
                        lookup_field,
                        service=_SERVICE,
                        extra_query_params=extra,
                        check_mode=check_mode,
                    )
                except ResourceNotFoundError as exc:
                    missing_reference = (exc.endpoint, exc.lookup_field, exc.service) == (lookup_endpoint, lookup_field, _SERVICE)
                    if not check_mode or not missing_reference:
                        raise
                    association_changed = True
                if association_changed:
                    changed = True
            if survey_spec is not None and manager.manage_sub_resource(BASE_PATH, wjt_id, "survey_spec", survey_spec, check_mode=check_mode):
                changed = True
        except Exception as exc:
            result["failed"] = True
            result["msg"] = "Failed to reconcile associations/survey_spec: %s" % exc
            return result

        try:
            if workflow_nodes:
                self._validate_workflow_nodes(manager, workflow_nodes)
            if destroy_current_nodes:
                if self._destroy_workflow_nodes(manager, wjt_id, check_mode):
                    changed = True
            if workflow_nodes:
                if self._manage_workflow_nodes(manager, wjt_id, workflow_nodes, check_mode):
                    changed = True
                if self._manage_workflow_node_associations(manager, wjt_id, workflow_nodes, check_mode):
                    changed = True
        except Exception as exc:
            result["failed"] = True
            result["msg"] = "Failed to reconcile workflow nodes: %s" % exc
            return result

        if changed:
            result["changed"] = True
        return result
