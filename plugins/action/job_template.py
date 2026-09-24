#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.job_template module.

Migrated from awx.awx/ansible.controller job_template module.
Uses Pattern C (custom run override) due to:
  - Association fields (credentials, labels, notification_templates, instance_groups)
  - Secondary endpoint (survey_spec)
  - Copy operation (copy_from)
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from typing import Any

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.job_template import (
    AnsibleJobTemplate,
)

logger = logging.getLogger(__name__)

_ASSOCIATION_FIELDS = (
    "credentials",
    "labels",
    "notification_templates_started",
    "notification_templates_success",
    "notification_templates_error",
    "instance_groups",
)

_JT_BASE_PATH = "/api/controller/v2/job_templates"

_ASSOCIATION_MAP = {
    "credentials": ("credentials", "name"),
    "labels": ("labels", "name"),
    "notification_templates_started": ("notification_templates", "name"),
    "notification_templates_success": ("notification_templates", "name"),
    "notification_templates_error": ("notification_templates", "name"),
    "instance_groups": ("instance_groups", "name"),
}


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for job_template module."""

    MODULE_NAME = "job_template"
    MODEL_CLASS = AnsibleJobTemplate
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset(
        {
            "copy_from",
            "survey_spec",
            "credentials",
            "labels",
            "notification_templates_started",
            "notification_templates_success",
            "notification_templates_error",
            "instance_groups",
        }
    )

    def _build_ansible_data(self, resource: Any, validated_params: dict, operation: str) -> dict:
        """Build ansible_data from explicitly-provided task parameters only.

        Prevents list fields (credentials, labels, etc.) defaulting to None
        from being sent to the API.
        """
        data = {k: getattr(resource, k) for k in validated_params if hasattr(resource, k)}
        if getattr(resource, "id", None) is not None:
            data["id"] = resource.id
        return data

    def run(self, tmp: object = None, task_vars: dict = None) -> dict:
        """Run the job_template action plugin.

        Extends the base run() to handle:
        - copy_from: Copy an existing job template before applying changes
        - Association fields: credentials, labels, notification_templates, instance_groups
        - survey_spec: Secondary endpoint for survey management

        All HTTP calls are delegated to the SDK layer (PlatformService / DirectHTTPClient).
        """
        copy_from = self._task.args.pop("copy_from", None)
        survey_spec = self._task.args.pop("survey_spec", None)
        state = self._task.args.get("state", "present")

        association_data = {}
        for field in _ASSOCIATION_FIELDS:
            val = self._task.args.pop(field, None)
            if val is not None:
                association_data[field] = val

        if copy_from and state not in ("absent", "deleted"):
            result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
            self._task_vars = task_vars or {}

            try:
                manager, facts_to_set = self._get_or_spawn_manager(task_vars or {})
                self._client = manager
                if facts_to_set:
                    result["ansible_facts"] = facts_to_set
                    result["_ansible_facts_cacheable"] = True

                copied = manager.copy_resource(
                    self.MODULE_NAME,
                    copy_from,
                    self._task.args.get("name"),
                    _JT_BASE_PATH,
                )

                if copied and copied.get("id"):
                    self._task.args["id"] = copied["id"]
                    result = super().run(tmp, task_vars)
                else:
                    result.update(changed=True, failed=False, **{self.MODULE_NAME: copied or {}})

            except Exception as exc:
                result.update(changed=False, failed=True, msg=str(exc))
                return result
        else:
            result = super().run(tmp, task_vars)

        if result.get("failed"):
            return result

        jt_id = result.get("id") or (result.get(self.MODULE_NAME, {}) or {}).get("id")

        if jt_id and state not in ("absent", "deleted", "exists"):
            manager = self._client
            if manager:
                for field, (lookup_ep, lookup_field) in _ASSOCIATION_MAP.items():
                    desired = association_data.get(field)
                    if desired is not None:
                        changed = manager.manage_associations(
                            _JT_BASE_PATH,
                            jt_id,
                            field,
                            desired,
                            lookup_ep,
                            lookup_field,
                        )
                        if changed:
                            result["changed"] = True

                if survey_spec is not None:
                    changed = manager.manage_sub_resource(
                        _JT_BASE_PATH,
                        jt_id,
                        "survey_spec",
                        survey_spec,
                    )
                    if changed:
                        result["changed"] = True

        return result
