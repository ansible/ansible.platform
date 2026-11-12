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


class WorkflowNodeNotFoundError(ValueError):
    """A requested node identifier was not found within the selected workflow."""


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "workflow_job_template_node"
    MODEL_CLASS = AnsibleWorkflowJobTemplateNode
    LOOKUP_FIELD = "identifier"

    _WRITE_ONLY_FIELDS = frozenset(set(_ASSOC_MAP) | {"approval_node"})
    _MUTUALLY_EXCLUSIVE = [["unified_job_template", "approval_node"]]
    _NULLABLE_FK_FIELDS = frozenset({"execution_environment"})

    def _build_argspec_from_docs(self, documentation: str) -> dict:
        """Validate approval suboptions before any resource lookup or mutation.

        Args:
            documentation: Module DOCUMENTATION YAML.

        Returns:
            dict: Argument specification with approval dictionary validation enabled.
        """
        argspec = super()._build_argspec_from_docs(documentation)
        approval = argspec["argument_spec"]["approval_node"]
        approval["options"] = approval.pop("suboptions")
        return argspec

    @staticmethod
    def _resolve_node_ids_in_workflow(manager, workflow_id, identifiers):
        """Resolve node identifiers to IDs scoped to a specific workflow.

        Always looks up by identifier within the workflow — numeric values
        are treated as identifiers, not database IDs, because node
        identifiers can legitimately be numeric strings like ``"123"``.
        """
        resolved = manager.lookup_resource_ids(
            "workflow_job_template_nodes",
            "identifier",
            identifiers,
            service=_SERVICE,
            extra_query_params={"workflow_job_template": workflow_id},
            numeric_is_id=False,
            allow_missing=True,
        )
        node_ids = []
        for ident in identifiers:
            key = str(ident)
            if key not in resolved:
                raise WorkflowNodeNotFoundError(f"Workflow node with identifier '{ident}' not found in workflow {workflow_id}")
            node_ids.append(resolved[key])
        return node_ids

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        association_data = {field: self._task.args.get(field) for field in _ASSOC_MAP}
        organization = self._task.args.get("organization")
        approval_node = self._task.args.get("approval_node")

        result = super().run(tmp, task_vars)

        state = self._task.args.get("state", "present")
        if result.get("failed") or state in ("absent", "exists"):
            return result

        node_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")
        if not node_id:
            return result

        node_data = result.get(self.MODULE_NAME) or {}
        wfjt_id = node_data.get("workflow_job_template")

        try:
            manager = self._client
            if wfjt_id is not None and not str(wfjt_id).strip().isdigit():
                wfjt_id = manager.lookup_resource_id("workflow_job_templates", "name", str(wfjt_id), service=_SERVICE)

            org_id = None
            if organization is not None:
                if not str(organization).strip().isdigit():
                    org_id = manager.lookup_resource_id("organizations", "name", str(organization), service="controller")
                else:
                    org_id = int(organization)
            org_scope = {"organization": org_id} if org_id is not None else None

            changed = False
            if approval_node is not None:
                result["workflow_node_id"] = node_id
                if manager.manage_workflow_approval(node_id, approval_node, check_mode=self._task.check_mode):
                    changed = True
            for field, (lookup_endpoint, lookup_field) in _ASSOC_MAP.items():
                desired = association_data.get(field)
                if desired is None:
                    continue
                if field in _NODE_ASSOC_FIELDS and wfjt_id:
                    try:
                        desired = self._resolve_node_ids_in_workflow(manager, wfjt_id, desired)
                    except WorkflowNodeNotFoundError:
                        if self._task.check_mode:
                            changed = True
                            continue
                        raise
                extra = org_scope if field == "labels" and org_scope else None
                if manager.manage_associations(
                    BASE_PATH,
                    node_id,
                    field,
                    desired,
                    lookup_endpoint,
                    lookup_field,
                    service=_SERVICE,
                    extra_query_params=extra,
                    check_mode=self._task.check_mode,
                ):
                    changed = True
        except Exception as exc:
            result["failed"] = True
            result["msg"] = "Failed to reconcile associations: %s" % exc
            return result

        if changed:
            result["changed"] = True
        return result
