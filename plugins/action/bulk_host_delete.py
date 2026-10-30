#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for bulk_host_delete module.

Deletes multiple hosts in a single POST to /api/controller/v2/bulk/host_delete/.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from dataclasses import asdict
from typing import Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.bulk_host_delete import AnsibleBulkHostDelete
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.bulk_host_delete import BulkHostDeleteTransformMixin_v2


def _get_error_response(exc: Exception) -> Optional[dict]:
    """Return an API error response in the legacy module's shape, if available."""
    error_details = getattr(exc, "details", None)
    if not isinstance(error_details, dict):
        error_details = {}

    status_code = error_details.get("status_code")
    response_body = error_details.get("response_body")
    body_is_json = response_body is not None and not isinstance(response_body, (str, bytes))

    if response_body is None:
        api_response = getattr(exc, "response", None)
        if api_response is not None:
            status_code = getattr(api_response, "status_code", status_code)
            try:
                response_body = api_response.json()
                body_is_json = True
            except (AttributeError, ValueError):
                response_body = getattr(api_response, "text", None)

    if response_body is None:
        return {"status_code": status_code} if status_code is not None else None

    if isinstance(response_body, bytes):
        response_body = response_body.decode("utf-8", errors="replace")
    if not body_is_json and isinstance(response_body, str):
        try:
            response_body = json.loads(response_body)
            body_is_json = True
        except ValueError:
            pass

    body_key = "json" if body_is_json else "text"
    return {"status_code": status_code, body_key: response_body}


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "bulk_host_delete"
    MODEL_CLASS = AnsibleBulkHostDelete
    LOOKUP_FIELD = "hosts"

    def run(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """Bulk delete hosts via the Controller bulk API.

        Args:
            tmp: Deprecated parameter.
            task_vars: Task variables dictionary.

        Returns:
            dict: Result with changed key.
        """
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            hosts = validated_params.get("hosts")

            if not hosts:
                raise AnsibleError("hosts is required and must be a non-empty list of host IDs")

            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "msg": f"Would delete {len(hosts)} host(s) (check mode)",
                    }
                )
                return result

            ansible_data = AnsibleBulkHostDelete(hosts=hosts)
            api_data = BulkHostDeleteTransformMixin_v2.from_ansible_data(ansible_data)
            create_operation = BulkHostDeleteTransformMixin_v2.get_endpoint_operations()["create"]
            manager.launch_resource(launch_url=create_operation.path, payload=asdict(api_data), service="controller", retry=False)

            result["changed"] = True

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            error_response = _get_error_response(exc)
            if error_response is not None:
                result["response"] = error_response
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
