#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.workflow_job_template_node import (
    AnsibleWorkflowJobTemplateNode,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.workflow_job_template_node import BASE_PATH

_ASSOC_MAP = {
    "success_nodes": ("workflow_job_template_nodes", "identifier"),
    "failure_nodes": ("workflow_job_template_nodes", "identifier"),
    "always_nodes": ("workflow_job_template_nodes", "identifier"),
    "credentials": ("credentials", "name"),
    "labels": ("labels", "name"),
    "instance_groups": ("instance_groups", "name"),
}

_SERVICE = "controller"
_NODE_ASSOC_FIELDS = frozenset({"success_nodes", "failure_nodes", "always_nodes"})


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "workflow_job_template_node"
    MODEL_CLASS = AnsibleWorkflowJobTemplateNode
    LOOKUP_FIELD = "identifier"

    _WRITE_ONLY_FIELDS = frozenset(_ASSOC_MAP)

    @staticmethod
    def _resolve_node_ids_in_workflow(manager, workflow_id, identifiers):
        """Resolve node identifiers to IDs scoped to a specific workflow."""
        resolved = []
        for ident in identifiers:
            if str(ident).strip().isdigit():
                resolved.append(int(ident))
                continue
            data = manager.search_api(
                f"{BASE_PATH}/?identifier={ident}&workflow_job_template={workflow_id}"
            )
            nodes = data.get("results", [])
            if not nodes:
                raise ValueError(f"Workflow node with identifier '{ident}' not found in workflow {workflow_id}")
            resolved.append(nodes[0]["id"])
        return resolved

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        association_data = {field: self._task.args.pop(field, None) for field in _ASSOC_MAP}

        result = super().run(tmp, task_vars)

        state = self._task.args.get("state", "present")
        if result.get("failed") or state in ("absent", "exists"):
            return result

        node_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")
        if not node_id:
            return result

        reconcile_fields = {k: v for k, v in association_data.items() if v is not None}
        if self._task.check_mode:
            if reconcile_fields:
                result["changed"] = True
            return result

        node_data = result.get(self.MODULE_NAME) or {}
        wfjt_id = node_data.get("workflow_job_template")

        try:
            manager = self._client
            changed = False
            for field, (lookup_endpoint, lookup_field) in _ASSOC_MAP.items():
                desired = association_data.get(field)
                if desired is None:
                    continue
                if field in _NODE_ASSOC_FIELDS and wfjt_id:
                    desired = self._resolve_node_ids_in_workflow(manager, wfjt_id, desired)
                if manager.manage_associations(
                    BASE_PATH, node_id, field, desired, lookup_endpoint, lookup_field, service=_SERVICE
                ):
                    changed = True
        except Exception as exc:
            result["failed"] = True
            result["msg"] = "Failed to reconcile associations: %s" % exc
            return result

        if changed:
            result["changed"] = True
        return result
