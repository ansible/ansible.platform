#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""Action plugin for ansible.platform.organization.

Gateway manages organization lifecycle and RBAC. This plugin also applies
optional Controller-owned settings and associations to the linked Controller
organization when those fields are supplied.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type
from dataclasses import asdict
from typing import Any, Dict, Optional

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_organization import AnsibleControllerOrganization
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.organization import AnsibleOrganization
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_organization import (
    BASE_PATH as CONTROLLER_ORGANIZATION_PATH,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_organization import (
    ControllerOrganizationTransformMixin_v2,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.gateway.v1.organization import OrganizationTransformMixin_v1
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import build_endpoint_request

_CONTROLLER_SETTINGS = ("default_environment", "max_hosts")
_CONTROLLER_ASSOCIATIONS = {
    "instance_groups": ("instance_groups", "name"),
    "notification_templates_started": ("notification_templates", "name"),
    "notification_templates_success": ("notification_templates", "name"),
    "notification_templates_error": ("notification_templates", "name"),
    "notification_templates_approvals": ("notification_templates", "name"),
    "galaxy_credentials": ("credentials", "name"),
}
_CONTROLLER_SERVICE = "controller"
_GATEWAY_ORGANIZATION_PATH = OrganizationTransformMixin_v1.get_endpoint_operations()["list"].path


class ActionModule(BaseResourceActionPlugin):
    """Manage Gateway organizations and optional Controller configuration."""

    MODULE_NAME = "organization"
    MODEL_CLASS = AnsibleOrganization
    _WRITE_ONLY_FIELDS = frozenset(_CONTROLLER_SETTINGS) | frozenset(_CONTROLLER_ASSOCIATIONS)

    def _prepare_action(self, tmp: Optional[object] = None, task_vars: Optional[dict] = None) -> dict:
        """Prepare Gateway CRUD and retain requested Controller-only fields.

        Controller settings are transformed into a sparse update payload.
        When Controller fields are requested, the Gateway organization is
        resolved to its Controller counterpart through the shared ansible_id.

        Args:
            tmp: Temporary directory passed through to the base action helper.
            task_vars: Ansible variables used to initialize the API manager.

        Returns:
            dict: Prepared action data returned by the base action helper.
        """
        prepared = super()._prepare_action(tmp, task_vars)
        params = prepared["validated_params"]
        self._controller_organization_id = None
        self._controller_update = None
        self._controller_update_template = None
        self._controller_settings = {}
        self._controller_associations = {}
        self._has_cached_gateway_find_result = False
        self._cached_gateway_find_result = None
        if params.get("state", "present") in ("absent", "exists"):
            return prepared
        settings = {field: params[field] for field in _CONTROLLER_SETTINGS if params.get(field) is not None}
        associations = {field: params[field] for field in _CONTROLLER_ASSOCIATIONS if params.get(field) is not None}
        self._controller_settings = settings
        self._controller_associations = associations
        if settings or associations:
            manager = prepared["manager"]
            update = ControllerOrganizationTransformMixin_v2.get_endpoint_operations()["update"]
            self._controller_update_template = update.path
            if settings:
                controller_resource = AnsibleControllerOrganization(**settings)
                api_data = ControllerOrganizationTransformMixin_v2.from_ansible_data(controller_resource, {"manager": manager})
                self._controller_update = build_endpoint_request(update, api_data)[1]
            else:
                self._controller_update = {}

            lookup_value = str(params["name"]).strip()
            if lookup_value.isdigit():
                gateway_id = int(lookup_value)
                try:
                    gateway_resource = manager.search_api("%s%s/" % (_GATEWAY_ORGANIZATION_PATH, gateway_id), service="gateway")
                except Exception as exc:
                    if not self._is_resource_not_found(exc):
                        raise
                    gateway_resource = None
                if gateway_resource:
                    self._cached_gateway_find_result = asdict(OrganizationTransformMixin_v1.from_api(gateway_resource, {"manager": manager}))
                    self._has_cached_gateway_find_result = True
            else:
                gateway_results = manager.search_api(
                    _GATEWAY_ORGANIZATION_PATH,
                    query_params={"name": params["name"]},
                    return_all=True,
                    service="gateway",
                ).get("results", [])
                gateway_matches = [item for item in gateway_results if item.get("name") == params["name"]]
                if len(gateway_matches) > 1:
                    raise ValueError("Expected one Gateway organization named %r; found %d" % (params["name"], len(gateway_matches)))
                gateway_resource = gateway_matches[0] if gateway_matches else None
                if gateway_resource:
                    self._cached_gateway_find_result = asdict(OrganizationTransformMixin_v1.from_api(gateway_resource, {"manager": manager}))
                    self._has_cached_gateway_find_result = True
                else:
                    self._cached_gateway_find_result = {}
                    self._has_cached_gateway_find_result = True

            if gateway_resource:
                try:
                    ansible_id = self._get_resource_ansible_id(gateway_resource, "Gateway")
                except ValueError:
                    gateway_id = gateway_resource.get("id")
                    if gateway_id is None:
                        raise ValueError("Gateway organization lookup result did not include an ID or shared ansible_id")
                    gateway_data = manager.search_api("%s%s/" % (_GATEWAY_ORGANIZATION_PATH, gateway_id), service="gateway")
                    ansible_id = self._get_resource_ansible_id(gateway_data, "Gateway")
                self._controller_organization_id = self._find_controller_organization_id(manager, ansible_id)
        return prepared

    def _find_existing_resource(self, manager: Any, resource_data: dict) -> dict:
        """Reuse the Gateway result fetched during Controller mapping preflight."""
        if self._has_cached_gateway_find_result:
            self._has_cached_gateway_find_result = False
            return self._cached_gateway_find_result
        return super()._find_existing_resource(manager, resource_data)

    @staticmethod
    def _get_resource_ansible_id(resource: Dict[str, Any], service_name: str) -> str:
        """Extract the shared resource UUID from an organization response.

        Args:
            resource: Gateway or Controller organization API response.
            service_name: Service name used to identify malformed responses.

        Returns:
            str: Shared ansible_id used to locate the linked organization.

        Raises:
            ValueError: If the response does not include the shared UUID.
        """
        summary_fields = resource.get("summary_fields") or {}
        resource_summary = summary_fields.get("resource") or {}
        ansible_id = resource_summary.get("ansible_id")
        if not ansible_id:
            raise ValueError("%s organization response did not include summary_fields.resource.ansible_id" % service_name)
        return ansible_id

    @staticmethod
    def _find_controller_organization_id(manager: Any, ansible_id: str) -> int:
        """Find exactly one Controller organization with the shared UUID.

        Args:
            manager: Platform API manager used for the Controller lookup.
            ansible_id: Shared UUID obtained from the Gateway organization.

        Returns:
            int: Controller organization ID, in Controller's ID space.

        Raises:
            ValueError: If zero or multiple matching organizations are found.
        """
        response = manager.search_api(
            CONTROLLER_ORGANIZATION_PATH,
            query_params={"resource__ansible_id": ansible_id},
            return_all=True,
            service=_CONTROLLER_SERVICE,
        )
        matches = []
        for item in response.get("results", []):
            summary_fields = item.get("summary_fields") or {}
            resource_summary = summary_fields.get("resource") or {}
            if resource_summary.get("ansible_id") == ansible_id:
                matches.append(item)
        if len(matches) != 1:
            raise ValueError("Expected one Controller organization with ansible_id %r; found %d" % (ansible_id, len(matches)))
        return matches[0]["id"]

    def run(self, tmp: Optional[object] = None, task_vars: Optional[Dict[str, Any]] = None) -> dict:
        """Run Gateway organization CRUD, then reconcile requested Controller fields.

        An omitted association field is left unchanged; an explicitly empty
        list clears that association. Controller API errors are returned as
        task failures.

        Args:
            tmp: Temporary directory passed through to the base action helper.
            task_vars: Ansible variables used to initialize the API manager.

        Returns:
            dict: Ansible result containing Gateway and requested Controller data.
        """
        result = super().run(tmp, task_vars)
        if result.get("failed") or self._task.args.get("state", "present") in ("absent", "exists"):
            return result

        settings = self._controller_settings
        associations = self._controller_associations
        if not settings and not associations:
            return result

        try:
            manager = self._client
            controller_id = self._controller_organization_id
            if controller_id is None:
                gateway_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")
                if gateway_id is None and self._task.check_mode:
                    resource_result = result.setdefault(self.MODULE_NAME, {})
                    for key, value in {**settings, **associations}.items():
                        resource_result[key] = value
                        result[key] = value
                    return result
                if gateway_id is None:
                    raise ValueError("Gateway organization result did not include an ID")
                gateway_data = manager.search_api("%s%s/" % (_GATEWAY_ORGANIZATION_PATH, gateway_id), service="gateway")
                ansible_id = self._get_resource_ansible_id(gateway_data, "Gateway")
                controller_id = self._find_controller_organization_id(manager, ansible_id)

            path = self._controller_update_template.replace("{id}", str(controller_id))
            payload = self._controller_update
            if payload:
                current = manager.search_api(path, service=_CONTROLLER_SERVICE)
                changed_fields = {}
                for key, value in payload.items():
                    current_value = current.get(key)
                    if isinstance(current_value, dict):
                        current_value = current_value.get("id")
                    if current_value != value:
                        changed_fields[key] = value

                if changed_fields:
                    if not self._task.check_mode:
                        manager.direct_request("PATCH", path, data=payload)
                    result["changed"] = True

            for field, (lookup_endpoint, lookup_field) in _CONTROLLER_ASSOCIATIONS.items():
                desired = associations.get(field)
                if desired is not None and manager.manage_associations(
                    CONTROLLER_ORGANIZATION_PATH,
                    controller_id,
                    field,
                    desired,
                    lookup_endpoint,
                    lookup_field,
                    service=_CONTROLLER_SERVICE,
                    check_mode=self._task.check_mode,
                ):
                    result["changed"] = True

            resource_result = result.setdefault(self.MODULE_NAME, {})
            for key, value in {**settings, **associations}.items():
                resource_result[key] = value
                result[key] = value
        except Exception as exc:
            result["failed"] = True
            result["msg"] = "Failed to reconcile Controller organization settings or associations: %s" % exc
        return result
