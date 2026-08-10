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
from typing import Any, List, Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.job_template import (
    AnsibleJobTemplate,
)

logger = logging.getLogger(__name__)

_ASSOCIATION_FIELDS = frozenset(
    {
        "credentials",
        "labels",
        "notification_templates_started",
        "notification_templates_success",
        "notification_templates_error",
        "instance_groups",
    }
)

_EXTRA_TASK_FIELDS = _ASSOCIATION_FIELDS | frozenset(
    {
        "survey_spec",
        "copy_from",
        "organization",
    }
)


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

    def _resolve_association_ids(
        self,
        manager,
        endpoint: str,
        lookup_field: str,
        items: List[str],
    ) -> List[int]:
        """Resolve a list of names/IDs to integer IDs."""
        resolved = []
        for item in items:
            if str(item).isdigit():
                resolved.append(int(item))
            else:
                try:
                    item_id = manager.lookup_resource_id(endpoint, lookup_field, str(item))
                    if item_id:
                        resolved.append(item_id)
                    else:
                        raise AnsibleError("Could not find %s entry with name '%s'" % (endpoint, item))
                except Exception as exc:
                    if "not found" in str(exc).lower():
                        raise AnsibleError("Could not find %s entry with name '%s'" % (endpoint, item))
                    raise
        return resolved

    def _handle_associations(self, manager, jt_id: int, result: dict, write_only_data: dict) -> None:
        """Manage association sub-endpoints for the job template.

        For each association field, resolve names to IDs and POST associate/disassociate
        calls to the appropriate sub-endpoint.
        """
        association_map = {
            "credentials": ("credentials", "name"),
            "labels": ("labels", "name"),
            "notification_templates_started": ("notification_templates", "name"),
            "notification_templates_success": ("notification_templates", "name"),
            "notification_templates_error": ("notification_templates", "name"),
            "instance_groups": ("instance_groups", "name"),
        }

        for field, (endpoint, lookup_field) in association_map.items():
            desired_items = write_only_data.get(field)
            if desired_items is None:
                continue

            desired_ids = self._resolve_association_ids(manager, endpoint, lookup_field, desired_items)

            # Get current associations
            assoc_endpoint = "/api/controller/v2/job_templates/%s/%s/" % (jt_id, field)
            try:
                current_response = manager.session.get(
                    manager._build_url(assoc_endpoint),
                )
                current_data = current_response.json() if current_response.status_code == 200 else {}
                current_results = current_data.get("results", [])
                current_ids = [item["id"] for item in current_results]
            except Exception:
                current_ids = []

            # Associate new items
            for item_id in desired_ids:
                if item_id not in current_ids:
                    try:
                        manager.session.post(
                            manager._build_url(assoc_endpoint),
                            json={"id": item_id, "associate": True},
                        )
                        result["changed"] = True
                    except Exception as exc:
                        logger.debug("Failed to associate %s %s: %s", field, item_id, exc)

            # Disassociate items not in desired list
            for item_id in current_ids:
                if item_id not in desired_ids:
                    try:
                        manager.session.post(
                            manager._build_url(assoc_endpoint),
                            json={"id": item_id, "disassociate": True},
                        )
                        result["changed"] = True
                    except Exception as exc:
                        logger.debug("Failed to disassociate %s %s: %s", field, item_id, exc)

    def _handle_survey_spec(self, manager, jt_id: int, result: dict, survey_spec: Optional[dict]) -> None:
        """Manage the survey_spec secondary endpoint."""
        if survey_spec is None:
            return

        spec_endpoint = "/api/controller/v2/job_templates/%s/survey_spec/" % jt_id

        if survey_spec == {}:
            # Empty dict means delete the survey
            try:
                response = manager.session.delete(manager._build_url(spec_endpoint))
                if response.status_code in (200, 204):
                    result["changed"] = True
            except Exception as exc:
                raise AnsibleError("Failed to delete survey: %s" % str(exc))
        else:
            # Check if survey already matches
            try:
                current_response = manager.session.get(manager._build_url(spec_endpoint))
                current_spec = current_response.json() if current_response.status_code == 200 else None
            except Exception:
                current_spec = None

            if survey_spec != current_spec:
                try:
                    response = manager.session.post(
                        manager._build_url(spec_endpoint),
                        json=survey_spec,
                    )
                    if response.status_code not in (200, 201):
                        error_msg = response.json().get("error", response.text) if response.text else "Unknown error"
                        raise AnsibleError("Failed to update survey: %s" % error_msg)
                    result["changed"] = True
                except AnsibleError:
                    raise
                except Exception as exc:
                    raise AnsibleError("Failed to update survey: %s" % str(exc))

    def _handle_copy(self, manager, copy_from: str, name: str, result: dict) -> Optional[dict]:
        """Handle copy_from: copy an existing job template.

        Returns the copied job template data dict, or None on failure.
        """
        # Find the source job template
        try:
            source = manager.execute(
                operation="find",
                module_name=self.MODULE_NAME,
                ansible_data={"name": copy_from},
            )
        except Exception:
            source = None

        if not source or not source.get("id"):
            # Try by ID
            if str(copy_from).isdigit():
                try:
                    source = manager.execute(
                        operation="find",
                        module_name=self.MODULE_NAME,
                        ansible_data={"id": int(copy_from)},
                    )
                except Exception:
                    source = None

        if not source or not source.get("id"):
            raise AnsibleError("Could not find job template '%s' to copy from" % copy_from)

        copy_endpoint = "/api/controller/v2/job_templates/%s/copy/" % source["id"]
        try:
            response = manager.session.post(
                manager._build_url(copy_endpoint),
                json={"name": name},
            )
            if response.status_code in (200, 201):
                result["changed"] = True
                return response.json()
            else:
                raise AnsibleError("Failed to copy job template: %s" % (response.text or "Unknown error"))
        except AnsibleError:
            raise
        except Exception as exc:
            raise AnsibleError("Failed to copy job template: %s" % str(exc))

    def run(self, tmp: object = None, task_vars: dict = None) -> dict:
        """Run the job_template action plugin.

        Extends the base run() to handle:
        - copy_from: Copy an existing job template before applying changes
        - Association fields: credentials, labels, notification_templates, instance_groups
        - survey_spec: Secondary endpoint for survey management
        """
        if task_vars is None:
            task_vars = {}

        # Capture extra fields before super().run() processes args
        copy_from = self._task.args.get("copy_from")
        survey_spec = self._task.args.get("survey_spec")
        state = self._task.args.get("state", "present")

        # Capture association field values
        association_data = {}
        for field in _ASSOCIATION_FIELDS:
            val = self._task.args.get(field)
            if val is not None:
                association_data[field] = val

        # Handle copy_from before the main CRUD
        if copy_from and state not in ("absent", "deleted"):
            # Remove copy_from from args so base doesn't see it
            self._task.args.pop("copy_from", None)

            # We need manager access for the copy
            result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
            self._task_vars = task_vars

            try:
                manager, facts_to_set = self._get_or_spawn_manager(task_vars)
                self._client = manager
                if facts_to_set:
                    result["ansible_facts"] = facts_to_set
                    result["_ansible_facts_cacheable"] = True

                name = self._task.args.get("name")
                copied = self._handle_copy(manager, copy_from, name, result)

                if copied and copied.get("id"):
                    # Now update the copied template with any additional params
                    self._task.args["id"] = copied["id"]
                    # Re-run through base to apply remaining params as an update
                    result = super().run(tmp, task_vars)
                else:
                    result.update(
                        {
                            "changed": True,
                            "failed": False,
                            self.MODULE_NAME: copied or {},
                        }
                    )

            except Exception as exc:
                result.update(
                    {
                        "changed": False,
                        "failed": True,
                        "msg": str(exc),
                    }
                )
                return result
        else:
            # Normal CRUD path
            self._task.args.pop("copy_from", None)
            result = super().run(tmp, task_vars)

        if result.get("failed"):
            return result

        # Post-CRUD: handle associations and survey_spec
        jt_id = result.get("id") or (result.get(self.MODULE_NAME, {}) or {}).get("id")

        if jt_id and state not in ("absent", "deleted", "exists"):
            manager = self._client
            if manager:
                # Handle association fields
                if association_data:
                    self._handle_associations(manager, jt_id, result, association_data)

                # Handle survey_spec
                if survey_spec is not None:
                    self._handle_survey_spec(manager, jt_id, result, survey_spec)

        return result
