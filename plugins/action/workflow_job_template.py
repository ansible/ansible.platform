#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.workflow_job_template module.

Migrated from awx.awx/ansible.controller workflow_job_template module. Uses
Pattern C (custom run override) due to:
  - Association fields (labels, notification_templates_started/success/error/approvals)
  - survey_spec sub-resource
  - Copy operation (copy_from)

Building the workflow's node graph (the legacy module's workflow_nodes /
schema option) is out of scope for this migration — see the ansible_models
module docstring for why.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from typing import Any

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.workflow_job_template import AnsibleWorkflowJobTemplate

logger = logging.getLogger(__name__)

_ASSOCIATION_FIELDS = (
    "labels",
    "notification_templates_started",
    "notification_templates_success",
    "notification_templates_error",
    "notification_templates_approvals",
)

_WORKFLOW_JOB_TEMPLATE_BASE_PATH = "/api/controller/v2/workflow_job_templates"

_ASSOCIATION_MAP = {
    "labels": ("/api/controller/v2/labels/", "name"),
    "notification_templates_started": ("/api/controller/v2/notification_templates/", "name"),
    "notification_templates_success": ("/api/controller/v2/notification_templates/", "name"),
    "notification_templates_error": ("/api/controller/v2/notification_templates/", "name"),
    "notification_templates_approvals": ("/api/controller/v2/notification_templates/", "name"),
}


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for workflow_job_template module."""

    MODULE_NAME = "workflow_job_template"
    MODEL_CLASS = AnsibleWorkflowJobTemplate
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset(_ASSOCIATION_FIELDS + ("copy_from", "survey_spec"))

    def _build_ansible_data(self, resource: Any, validated_params: dict, operation: str) -> dict:
        """Build ansible_data from explicitly-provided task parameters only."""
        data = {k: getattr(resource, k) for k in validated_params if hasattr(resource, k)}
        if getattr(resource, "id", None) is not None:
            data["id"] = resource.id
        return data

    def run(self, tmp: object = None, task_vars: dict = None) -> dict:
        """Run the workflow_job_template action plugin.

        Extends the base run() to handle:
        - copy_from: Copy an existing workflow_job_template before applying changes
        - survey_spec: GET/compare/POST or DELETE the survey sub-resource
        - Association fields: labels, notification_templates_*

        All HTTP calls are delegated to the SDK layer (PlatformService / DirectHTTPClient).
        """
        copy_from = self._task.args.pop("copy_from", None)
        survey_spec = self._task.args.pop("survey_spec", None)
        state = self._task.args.get("state", "present")

        association_data = {}
        for field in _ASSOCIATION_FIELDS:
            val = self._task.args.pop(field, None)
            if val is not None:
                # Popped before BaseResourceActionPlugin.run() validates self._task.args,
                # so the documented list/elements:str constraint never runs on these —
                # restore the minimum check that protects manage_associations() from
                # silently iterating a wrong-typed value (e.g. a bare string) character by
                # character instead of failing clearly.
                if not isinstance(val, list):
                    return {
                        "changed": False,
                        "failed": True,
                        "msg": "argument '%s' is of type %s and we were unable to convert to a list" % (field, type(val).__name__),
                    }
                association_data[field] = val

        if copy_from and state not in ("absent", "deleted"):
            result = {}
            try:
                prepared = self._prepare_action(tmp, task_vars)
                result = prepared["result"]
                manager = prepared["manager"]

                # Idempotency: copy_from should only ever seed a brand-new resource. If
                # a resource with the target name (scoped by organization) already
                # exists, skip copy_resource and fall through to a normal find-or-update
                # run instead — otherwise every re-run would create another copy.
                existing = None
                try:
                    existing = manager.execute(
                        operation="find",
                        module_name=self.MODULE_NAME,
                        ansible_data={"name": self._task.args.get("name"), "organization": self._task.args.get("organization")},
                    )
                except Exception:
                    existing = None

                if existing and existing.get("id"):
                    result = super().run(tmp, task_vars)
                else:
                    copied = manager.copy_resource(
                        self.MODULE_NAME,
                        copy_from,
                        self._task.args.get("name"),
                        _WORKFLOW_JOB_TEMPLATE_BASE_PATH,
                    )

                    if copied and copied.get("id"):
                        result = super().run(tmp, task_vars)
                        # copy_resource() always creates a new resource — that's a change even
                        # if the follow-up update-with-remaining-params finds nothing left to
                        # change and would otherwise report changed=False on its own.
                        result["changed"] = True
                    else:
                        result.update(changed=True, failed=False, **{self.MODULE_NAME: copied or {}})

            except Exception as exc:
                result.update(changed=False, failed=True, msg=str(exc))
                return result
        else:
            result = super().run(tmp, task_vars)

        if result.get("failed"):
            return result

        workflow_job_template_id = result.get("id") or (result.get(self.MODULE_NAME, {}) or {}).get("id")

        # check_mode: base_action.py's own create/update short-circuit happens before
        # this point, but for an *update* to an already-existing resource it still
        # returns the real id — skip the survey/association sync entirely so
        # check_mode never issues real writes.
        if workflow_job_template_id and state not in ("absent", "deleted", "exists") and not self._task.check_mode:
            manager = self._client
            if manager:
                if survey_spec is not None:
                    changed = manager.manage_sub_resource(
                        _WORKFLOW_JOB_TEMPLATE_BASE_PATH,
                        workflow_job_template_id,
                        "survey_spec",
                        data=survey_spec,
                    )
                    if changed:
                        result["changed"] = True

                for field, (lookup_ep, lookup_field) in _ASSOCIATION_MAP.items():
                    desired = association_data.get(field)
                    if desired is not None:
                        changed = manager.manage_associations(
                            _WORKFLOW_JOB_TEMPLATE_BASE_PATH,
                            workflow_job_template_id,
                            field,
                            desired,
                            lookup_ep,
                            lookup_field,
                        )
                        if changed:
                            result["changed"] = True

        return result
