#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.role_user_assignment import AnsibleRoleUserAssignment


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "role_user_assignment"
    MODEL_CLASS = AnsibleRoleUserAssignment
    LOOKUP_FIELD = "id"

    def _resolve_fks_to_strings(self, manager, data_dict):
        """Helper to safely resolve and cast foreign keys for users."""
        if "role_definition" in data_dict:
            if not str(data_dict["role_definition"]).isdigit():
                try:
                    resolved_id = manager.lookup_resource_id("role_definitions", "name", data_dict["role_definition"])
                    data_dict["role_definition"] = str(resolved_id)
                except Exception as e:
                    raise ValueError("Role definition lookup failed: %s" % e)
            else:
                data_dict["role_definition"] = str(data_dict["role_definition"])

        if "user" in data_dict:
            if not str(data_dict["user"]).isdigit():
                try:
                    resolved_id = manager.lookup_resource_id("users", "username", data_dict["user"])
                    data_dict["user"] = str(resolved_id)
                except Exception as e:
                    raise ValueError("User lookup failed: %s" % e)
            else:
                data_dict["user"] = str(data_dict["user"])

        return data_dict

    def run(self, tmp=None, task_vars=None):
        """
        Custom run() for role_user_assignment.

        Supports three object-selection modes:
        - object_id (scalar): standard single-object path via _run_standard().
        - object_ids (list): iterate, resolving each entry -> object_id, then
          idempotent create/delete per object.
        - Neither: system-wide assignment, single-object path.
        """
        if task_vars is None:
            task_vars = {}
        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            # ---- validate input ------------------------------------------------
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError("Could not load DOCUMENTATION for %s module" % self.MODULE_NAME)
            validated_input = self._validate_data(self._task.args.copy(), argspec, "input")
            validated_params = validated_input.validated_parameters

            # ---- manager connection --------------------------------------------
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            state = validated_params.get("state", "present")
            object_ids_raw = validated_params.get("object_ids") or []

            if not object_ids_raw:
                # ---- single-object path ---------------------------------------
                return self._run_standard(result, manager, argspec, validated_params, state)

            # ---- multi-object path: iterate over object_ids ------------------
            # Base data (role + user, shared across all assignments)
            _skip = self._AUTH_PARAMS | {"object_ids", "state", "object_id"}
            base_data = {k: v for k, v in validated_params.items() if v is not None and k not in _skip}

            # Apply FK Resolution and Casting
            base_data = self._resolve_fks_to_strings(manager, base_data)

            all_changed = False
            assignments = []

            for raw_oid in object_ids_raw:
                # Build per-object data: set object_id to each list entry.
                # from_ansible_data's existing FK resolver handles str->int
                # resolution (via role_definition-type-aware endpoint probing).
                per_obj = dict(base_data)
                per_obj["object_id"] = str(raw_oid)

                if state == "present":
                    # Idempotency: find existing assignment
                    try:
                        find_result = manager.execute(
                            operation="find",
                            module_name=self.MODULE_NAME,
                            ansible_data=per_obj,
                        )
                        if find_result and find_result.get("id"):
                            assignments.append(find_result)
                            continue  # already exists — no change
                    except Exception:
                        pass

                    # Create
                    mgr_result = manager.execute(
                        operation="create",
                        module_name=self.MODULE_NAME,
                        ansible_data=per_obj,
                    )
                    if mgr_result.get("failed", False):
                        result["failed"] = True
                        result["msg"] = mgr_result.get("msg", "Unknown error during creation.")
                        return result

                    all_changed = True
                    assignments.append(mgr_result)

                elif state == "absent":
                    try:
                        find_result = manager.execute(
                            operation="find",
                            module_name=self.MODULE_NAME,
                            ansible_data=per_obj,
                        )
                        if find_result and find_result.get("id"):
                            delete_payload = dict(per_obj)
                            delete_payload["id"] = find_result["id"]
                            mgr_result = manager.execute(
                                operation="delete",
                                module_name=self.MODULE_NAME,
                                ansible_data=delete_payload,
                            )

                            if mgr_result.get("failed", False):
                                result["failed"] = True
                                result["msg"] = mgr_result.get("msg", "Unknown error during deletion.")
                                return result

                            all_changed = True
                    except Exception as exc:
                        result["failed"] = True
                        result["msg"] = "Multi-object delete failed: %s" % str(exc)
                        return result

                elif state == "exists":
                    # Check existence without modifying; collect found assignments
                    try:
                        find_result = manager.execute(
                            operation="find",
                            module_name=self.MODULE_NAME,
                            ansible_data=per_obj,
                        )
                        if find_result and find_result.get("id"):
                            assignments.append(find_result)
                    except Exception:
                        pass

            if state == "exists" and not assignments:
                raise ValueError("No %s found matching the given criteria" % self.MODULE_NAME)

            _strip = (
                self._ANSIBLE_DIRECTIVES
                | (self._READ_ONLY_FIELDS - {"id"})
                | {
                    "changed",
                    "object_ids",
                    "assignments",
                }
            )
            primary = assignments[0] if assignments else {}
            clean = {k: v for k, v in primary.items() if k not in _strip}

            result.update(
                {
                    "changed": all_changed,
                    "failed": False,
                    self.MODULE_NAME: clean,
                    # Flat top-level keys kept for backward compatibility with
                    # playbooks written against <=2.6.
                    **clean,
                }
            )
            if len(assignments) > 1:
                result["assignments"] = [{k: v for k, v in a.items() if k not in _strip} for a in assignments]

        except Exception as exc:
            # Catch everything and return it cleanly as a dictionary so failed_when can intercept it
            result["failed"] = True
            result["msg"] = str(exc)

        return result

    # ------------------------------------------------------------------
    def _run_standard(self, result, manager, argspec, validated_params, state):
        """Single-object / system-wide path: standard present/absent logic."""
        from dataclasses import asdict

        resource_data = {k: v for k, v in validated_params.items() if v is not None and k not in self._AUTH_PARAMS and k != "object_ids"}

        try:
            resource_data = self._resolve_fks_to_strings(manager, resource_data)
        except Exception as exc:
            result["failed"] = True
            result["msg"] = str(exc)
            return result

        if "object_id" in resource_data and resource_data["object_id"] is not None:
            resource_data["object_id"] = str(resource_data["object_id"])

        try:
            resource = self.MODEL_CLASS(**resource_data)
        except TypeError as exc:
            result["failed"] = True
            result["msg"] = str(exc)
            return result

        operation = self._detect_operation(validated_params)

        _strip = (
            self._ANSIBLE_DIRECTIVES
            | (self._READ_ONLY_FIELDS - {"id"})
            | {
                "changed",
                "object_ids",
                "assignments",
            }
        )

        if state == "present" and operation == "create":
            try:
                find_result = manager.execute(
                    operation="find",
                    module_name=self.MODULE_NAME,
                    ansible_data=resource_data,
                )
                if find_result and find_result.get("id"):
                    if not self._should_update(resource_data, find_result):
                        clean = {k: v for k, v in find_result.items() if k not in _strip}
                        result.update(
                            {
                                "changed": False,
                                "failed": False,
                                self.MODULE_NAME: clean,
                                # Flat top-level keys kept for backward compatibility with
                                # playbooks written against <=2.6.
                                **clean,
                            }
                        )
                        return result
                    operation = "update"
                    resource.id = find_result["id"]
            except Exception:
                pass

        if operation == "delete" and not getattr(resource, "id", None):
            try:
                find_result = manager.execute(
                    operation="find",
                    module_name=self.MODULE_NAME,
                    ansible_data=resource_data,
                )
                if find_result and find_result.get("id"):
                    resource.id = find_result["id"]
                else:
                    result.update(
                        {
                            "changed": False,
                            "failed": False,
                            self.MODULE_NAME: {"state": "absent"},
                        }
                    )
                    return result
            except Exception:
                result.update(
                    {
                        "changed": False,
                        "failed": False,
                        self.MODULE_NAME: {"state": "absent"},
                    }
                )
                return result

        ansible_data = asdict(resource)
        manager_result = manager.execute(
            operation=operation,
            module_name=self.MODULE_NAME,
            ansible_data=ansible_data,
        )

        clean = {k: v for k, v in manager_result.items() if k not in _strip}

        is_failed = manager_result.get("failed", False)

        result.update(
            {
                "changed": manager_result.get("changed", False),
                "failed": is_failed,
                self.MODULE_NAME: clean,
                **(clean if operation != "delete" else {}),
            }
        )

        if is_failed and "msg" in manager_result:
            result["msg"] = manager_result["msg"]

        if operation == "delete":
            result[self.MODULE_NAME]["state"] = "absent"

        return result
