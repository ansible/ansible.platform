#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.application module.

CRUD via the persistent connection manager and API v1 transform mixins.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
import time
from dataclasses import asdict
from typing import Any, Dict, Optional, Union

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.application import AnsibleApplication


logger = logging.getLogger(__name__)


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "application"

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}
        self._task_vars = task_vars

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp
        action_start = time.perf_counter()

        auth_params = [
            "gateway_hostname",
            "gateway_username",
            "gateway_password",
            "gateway_token",
            "gateway_validate_certs",
            "gateway_request_timeout",
            "aap_hostname",
            "aap_username",
            "aap_password",
            "aap_token",
            "aap_validate_certs",
            "aap_request_timeout",
        ]

        def _resolve_fk_id(manager, endpoint: str, lookup_field: str, value: Optional[Union[str, int]]):
            if value is None:
                return None
            s = str(value).strip()
            if not s:
                return None
            if s.isdigit():
                return int(s)
            try:
                return manager.lookup_resource_id(endpoint, lookup_field, s)
            except Exception:
                return None

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError("Could not load DOCUMENTATION for application module")

            validated_input = self._validate_data(self._task.args.copy(), argspec, "input")
            validated_params = validated_input.validated_parameters

            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager
            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            app_data = {k: v for k, v in validated_params.items() if v is not None and k not in auth_params}
            app_name = app_data.get("name")
            name_is_id = app_name is not None and str(app_name).strip().isdigit()

            # Resolve FKs to numeric IDs so comparisons are stable.
            if "organization" in app_data:
                app_data["organization"] = _resolve_fk_id(manager, "organizations", "name", app_data.get("organization"))
            if "new_organization" in app_data and app_data.get("new_organization") is not None:
                app_data["new_organization"] = _resolve_fk_id(
                    manager, "organizations", "name", app_data.get("new_organization")
                )
            if "user" in app_data and app_data.get("user") is not None:
                app_data["user"] = _resolve_fk_id(manager, "users", "username", app_data.get("user"))

            app = AnsibleApplication(**app_data)
            operation = self._detect_operation(validated_params)

            def _find_payload():
                payload: Dict[str, Any] = {"name": app.name}
                if getattr(app, "organization", None) is not None:
                    payload["organization"] = app.organization
                # If name was actually an ID, prefer GET-by-id.
                if app.name is not None and str(app.name).strip().isdigit():
                    payload["id"] = int(str(app.name).strip())
                return payload

            # CREATE(present): find by (name, organization) to decide create vs update
            if operation == "create" and validated_params.get("state") == "present":
                try:
                    find_result = manager.execute(
                        operation="find",
                        module_name=self.MODULE_NAME,
                        ansible_data=_find_payload(),
                    )
                    if find_result and find_result.get("id"):
                        operation = "update"
                        app.id = find_result.get("id")
                        # Ensure name is correct after GET-by-id.
                        if name_is_id:
                            app.name = find_result.get("name", app.name)
                except Exception:
                    pass

            # DELETE(absent): find to obtain id if not provided.
            if operation == "delete" and not getattr(app, "id", None):
                try:
                    find_result = manager.execute(
                        operation="find",
                        module_name=self.MODULE_NAME,
                        ansible_data=_find_payload(),
                    )
                    if find_result and find_result.get("id"):
                        app.id = find_result.get("id")
                        if name_is_id:
                            app.name = find_result.get("name", app.name)
                    else:
                        result.update(
                            {
                                "changed": False,
                                "failed": False,
                                self.MODULE_NAME: {"state": "absent"},
                                "msg": "Application '%s' does not exist (already absent)" % app.name,
                            }
                        )
                        return result
                except Exception:
                    result.update(
                        {
                            "changed": False,
                            "failed": False,
                            self.MODULE_NAME: {"state": "absent"},
                            "msg": "Application '%s' does not exist (already absent)" % app.name,
                        }
                    )
                    return result

            # enforced is not used by current integration tests; treat it as update.
            if operation == "enforced":
                operation = "update"

            ansible_data = asdict(app)
            if operation == "update" and validated_params.get("state") == "enforced":
                ansible_data["_platform_enforced"] = True

            # Check mode: avoid create/update/delete calls.
            if self._task.check_mode and operation in ("create", "update", "delete"):
                result.update(
                    {
                        "changed": True if operation != "delete" else bool(getattr(app, "id", None)),
                        "failed": False,
                        self.MODULE_NAME: {"name": app.name, "state": "absent"}
                        if operation == "delete"
                        else {"name": app.name},
                        "id": getattr(app, "id", None),
                        "name": app.name,
                    }
                )
                return result

            manager_result = manager.execute(
                operation=operation,
                module_name=self.MODULE_NAME,
                ansible_data=ansible_data,
            )

            read_only_fields = {"id", "created", "modified", "url"}
            argspec_fields = set(argspec.get("argument_spec", {}).keys())
            filtered_result = {k: v for k, v in manager_result.items() if k in argspec_fields or k in read_only_fields}

            try:
                validated_output = self._validate_data(
                    {k: v for k, v in filtered_result.items() if k in argspec_fields},
                    argspec,
                    "output",
                )
                for field in read_only_fields:
                    if field in filtered_result:
                        validated_output[field] = filtered_result[field]
            except Exception:
                validated_output = manager_result

            result.update(
                {
                    "changed": manager_result.get("changed", False),
                    "failed": False,
                    self.MODULE_NAME: validated_output,
                    "id": validated_output.get("id"),
                    "name": validated_output.get("name"),
                }
            )

            if operation == "find":
                result["exists"] = bool(validated_output.get("id"))
            elif operation == "delete":
                result[self.MODULE_NAME]["state"] = "absent"

            timing = manager_result.get("_timing", {})
            result.setdefault("_timing", {})["action_plugin_time"] = time.perf_counter() - action_start
            result["_timing"]["manager_processing_time"] = timing.get("manager_processing_time", 0)
            result["_timing"]["api_call_time"] = timing.get("api_call_time", 0)

        except Exception as e:
            import traceback

            self._display.vvv("Error in application action plugin: %s" % e)
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
