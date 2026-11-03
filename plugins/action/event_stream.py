#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.event_stream module.

Manages EDA event streams via the standard CRUD state machine provided
by BaseResourceActionPlugin.  Field renames (forward_events -> test_mode,
headers -> additional_data_headers) and FK resolution (credential_name,
organization_name) are handled by the transform layer.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from typing import Any, Optional

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.event_stream import AnsibleEventStream
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.event_stream import EventStreamTransformMixin_v1


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for event_stream module."""

    MODULE_NAME = "event_stream"
    MODEL_CLASS = AnsibleEventStream
    LOOKUP_FIELD = "name"

    _DEPRECATED_FIELDS = {
        "event_stream_type": (
            "The event_stream_type parameter is deprecated and will be removed in version 3.0.0.",
            "3.0.0",
        ),
    }

    # credential_name and organization_name are FK fields whose values can
    # change via update.  Suppress the non-digit-name vs digit-string skip
    # in _should_update() so genuine FK changes trigger the update path.
    _MUTABLE_FK_FIELDS = frozenset({"credential_name", "organization_name"})

    def _prepare_action(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """Keep the documented forward_events default from becoming an update request.

        Args:
            tmp: Temporary directory passed through to the base action.
            task_vars: Ansible task variables used to initialize the manager.

        Returns:
            dict: Prepared inputs with forward_events omitted when it was not
                explicitly set for a non-enforced task.
        """
        prepared = super()._prepare_action(tmp, task_vars)
        if prepared["validated_params"].get("state", "present") != "enforced" and "forward_events" not in self._task.args:
            prepared["resource_data"].pop("forward_events", None)
        return prepared

    def _find_existing_resource(self, manager: Any, resource_data: dict) -> dict:
        """Find by the original name and recognize a completed rename.

        Args:
            manager: Client used to query the API.
            resource_data: Validated event stream fields.

        Returns:
            dict: The matching event stream, including a matching rename target.
        """
        try:
            existing = super()._find_existing_resource(manager, resource_data)
        except Exception as exc:
            new_name = resource_data.get("new_name")
            if not new_name or resource_data.get("state") in ("absent", "exists") or not self._is_resource_not_found(exc):
                raise

            renamed_data = dict(resource_data)
            renamed_data["name"] = new_name
            renamed_data.pop("new_name", None)
            try:
                rename_target = super()._find_existing_resource(manager, renamed_data)
            except Exception as target_exc:
                if self._is_resource_not_found(target_exc):
                    raise exc
                raise

            if self._should_update(resource_data, rename_target):
                raise ValueError(
                    "Cannot verify event stream rename from '%s' to '%s': the original was not found and the target does not match the requested state"
                    % (resource_data.get("name"), new_name)
                ) from exc
            return rename_target

        new_name = resource_data.get("new_name")
        if not new_name or new_name == resource_data.get("name") or resource_data.get("state") == "absent":
            return existing

        renamed_data = dict(resource_data)
        renamed_data["name"] = new_name
        renamed_data.pop("new_name", None)
        try:
            rename_target = super()._find_existing_resource(manager, renamed_data)
        except Exception as exc:
            if self._is_resource_not_found(exc):
                return existing
            raise

        existing_id = existing.get("id")
        target_id = rename_target.get("id")
        if existing_id is None or target_id is None or str(existing_id) != str(target_id):
            raise ValueError("Cannot rename event stream '%s': event stream '%s' already exists" % (resource_data.get("name"), new_name))

        return existing

    def _should_update(self, desired_data: dict, current_data: dict) -> bool:
        """Compare references by ID and treat an applied rename as converged.

        Args:
            desired_data: Explicitly requested event stream fields.
            current_data: Event stream returned by the API.

        Returns:
            bool: True when the API resource needs an update.
        """
        desired = dict(desired_data)
        new_name = desired.get("new_name")
        if new_name:
            if current_data.get("name") != new_name:
                return True
            desired["name"] = new_name
            desired.pop("new_name", None)

        manager = getattr(self, "_client", None)
        for field, endpoint in (("organization_name", "organizations"), ("credential_name", "eda-credentials")):
            desired_value = desired.get(field)
            current_value = current_data.get(field)
            if desired_value is None or field not in current_data:
                continue
            if current_value is None:
                return True
            if str(desired_value) == str(current_value):
                desired.pop(field, None)
                continue

            desired_org_id = None
            current_org_id = None
            if endpoint == "eda-credentials":
                desired_org = desired_data.get("organization_name")
                current_org = current_data.get("organization_name")
                if desired_org is not None:
                    desired_org_id = EventStreamTransformMixin_v1.resolve_reference_id(manager, "organizations", desired_org)
                    if current_org is None:
                        return True
                    current_org_id = EventStreamTransformMixin_v1.resolve_reference_id(manager, "organizations", current_org)
                    if desired_org_id != current_org_id:
                        return True
                elif current_org is not None:
                    current_org_id = EventStreamTransformMixin_v1.resolve_reference_id(manager, "organizations", current_org)

            desired_scope = {"organization": desired_org_id} if desired_org_id is not None else None
            current_scope = {"organization": current_org_id} if current_org_id is not None else None
            desired_id = EventStreamTransformMixin_v1.resolve_reference_id(manager, endpoint, desired_value, extra_query_params=desired_scope)
            current_id = EventStreamTransformMixin_v1.resolve_reference_id(manager, endpoint, current_value, extra_query_params=current_scope)
            if desired_id != current_id:
                return True
            desired.pop(field, None)

        return super()._should_update(desired, current_data)
