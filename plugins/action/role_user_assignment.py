#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.role_user_assignment import AnsibleRoleUserAssignment


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "role_user_assignment"
    MODEL_CLASS = AnsibleRoleUserAssignment
    LOOKUP_FIELD = "id"
    _WRITE_ONLY_FIELDS = frozenset({"object_ids"})
    _PRESERVE_RESULT_ID_FIELDS = frozenset({"object_id"})
    _MUTUALLY_EXCLUSIVE = [
        ["object_id", "object_ids"],
        ["object_id", "object_ansible_id"],
        ["object_ids", "object_ansible_id"],
        ["user", "user_ansible_id"],
    ]

    def run(self, tmp=None, task_vars=None):
        """
        Custom run() for role_user_assignment.

        Supports three object-selection modes:
        - object_id/object_ansible_id (scalar): standard path via the base class,
          except state=exists, which shares the multi-object result contract.
        - object_ids (list): iterate, resolving each entry -> object_id, then
          idempotent create/delete per object.
        - Neither: system-wide assignment, single-object path via the base class.
        """
        task_args = self._task.args
        state = task_args.get("state", "present")
        has_scalar_selector = task_args.get("object_id") is not None or bool(task_args.get("object_ansible_id"))
        if not task_args.get("object_ids") and not (state == "exists" and has_scalar_selector):
            return super().run(tmp, task_vars)

        if task_vars is None:
            task_vars = {}
        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            # ---- validate input ------------------------------------------------
            validated_params = self._validate_action_input().validated_params

            # ---- manager connection --------------------------------------------
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            state = validated_params.get("state", "present")
            check_mode = getattr(self._task, "check_mode", False)
            object_ids_raw = validated_params.get("object_ids") or []
            if state == "exists" and not object_ids_raw:
                if validated_params.get("object_id") is not None:
                    object_ids_raw = [{"object_id": validated_params["object_id"]}]
                elif validated_params.get("object_ansible_id"):
                    object_ids_raw = [{"object_ansible_id": validated_params["object_ansible_id"]}]

            # ---- multi-object path: iterate over object_ids ------------------
            # Base data (role + user, shared across all assignments)
            _skip = self._AUTH_PARAMS | {"object_ids", "state", "object_id", "object_ansible_id"}
            base_data = {k: v for k, v in validated_params.items() if v is not None and k not in _skip}

            all_changed = False
            assignments = []

            for raw_oid in object_ids_raw:
                # Build per-object data: set object_id to each list entry.
                # from_ansible_data's existing FK resolver handles str->int
                # resolution (via role_definition-type-aware endpoint probing).
                per_obj = dict(base_data)
                if isinstance(raw_oid, dict):
                    per_obj.update(raw_oid)
                else:
                    per_obj["object_id"] = raw_oid

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
                    except Exception as exc:
                        if not (self._is_resource_not_found(exc) or self._is_resource_scope_mismatch(exc)):
                            raise

                    if check_mode:
                        all_changed = True
                        assignments.append({"id": None, **per_obj})
                        continue

                    # Create
                    mgr_result = manager.execute(
                        operation="create",
                        module_name=self.MODULE_NAME,
                        ansible_data=per_obj,
                    )
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
                            if check_mode:
                                all_changed = True
                                continue
                            manager.execute(
                                operation="delete",
                                module_name=self.MODULE_NAME,
                                ansible_data={"id": find_result["id"]},
                            )
                            all_changed = True
                    except Exception as exc:
                        if not (self._is_resource_not_found(exc) or self._is_resource_scope_mismatch(exc)):
                            raise

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
                    except Exception as exc:
                        if not (self._is_resource_not_found(exc) or self._is_resource_scope_mismatch(exc)):
                            raise

            # ---- build clean result -------------------------------------------
            _strip = self._ANSIBLE_DIRECTIVES | (self._READ_ONLY_FIELDS - {"id"}) | {"changed", "object_ids", "assignments"}

            # A state=exists miss fails for both scalar and list selectors. Keep
            # a stable empty resource mapping so callers can inspect the result.
            if state == "exists" and not assignments:
                result.update(
                    {
                        "changed": False,
                        "failed": True,
                        "exists": False,
                        self.MODULE_NAME: {},
                        "msg": "No %s found matching the given criteria" % self.MODULE_NAME,
                    }
                )
                return result

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
            if state == "exists":
                result["exists"] = True
            if len(assignments) > 1:
                result["assignments"] = [{k: v for k, v in a.items() if k not in _strip} for a in assignments]

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
