#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.role_team_assignment import AnsibleRoleTeamAssignment


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "role_team_assignment"
    MODEL_CLASS = AnsibleRoleTeamAssignment
    LOOKUP_FIELD = "id"

    def run(self, tmp=None, task_vars=None):
        """
        Custom run() for role_team_assignment.

        Supports two modes:
        - Single-object (object_id / object_ansible_id): delegates to the
          standard BaseResourceActionPlugin.run() after stripping
          assignment_objects from task args.
        - Multi-object (assignment_objects list): iterates over each entry,
          resolves name+type -> object_id, and creates/deletes individual
          assignments with idempotency.
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
            assignment_objects_raw = validated_params.get("assignment_objects") or []

            if not assignment_objects_raw:
                # ---- single-object path: standard run logic -------------------
                return self._run_standard(result, manager, argspec, validated_params, state)

            # ---- multi-object path: iterate over assignment_objects -----------
            # Base data shared across all assignments (role + team, no object_id)
            _skip = self._AUTH_PARAMS | {
                "assignment_objects",
                "state",
                "object_id",
                "object_ids",
                "object_ansible_id",
            }
            base_data = {k: v for k, v in validated_params.items() if v is not None and k not in _skip}

            all_changed = False
            assignments = []

            for obj in assignment_objects_raw:
                per_obj = dict(base_data)

                # Resolve this entry's object identity
                if obj.get("object_id") is not None:
                    per_obj["object_id"] = obj["object_id"]
                elif obj.get("object_ansible_id"):
                    per_obj["object_ansible_id"] = obj["object_ansible_id"]
                elif obj.get("name") and obj.get("type"):
                    try:
                        oid = manager.lookup_resource_id(obj["type"], "name", obj["name"])
                        per_obj["object_id"] = oid
                    except Exception:
                        # If lookup fails, pass the name — from_ansible_data
                        # will attempt its own FK resolution.
                        per_obj["object_id"] = obj["name"]

                if state == "present":
                    # Idempotency: check if assignment already exists
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
                            manager.execute(
                                operation="delete",
                                module_name=self.MODULE_NAME,
                                ansible_data={"id": find_result["id"]},
                            )
                            all_changed = True
                    except Exception:
                        pass

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

            # For state=exists: fail (without setting MODULE_NAME key) if nothing
            # was found — mirrors the single-object path's "not found" behaviour.
            if state == "exists" and not assignments:
                raise ValueError("No %s found matching the given criteria" % self.MODULE_NAME)

            # ---- build clean result -------------------------------------------
            _strip = self._ANSIBLE_DIRECTIVES | (self._READ_ONLY_FIELDS - {"id"}) | {"changed", "assignment_objects", "assignments"}
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
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result

    # ------------------------------------------------------------------
    def _run_standard(self, result, manager, argspec, validated_params, state):
        """Single-object path: mirrors the standard BaseResourceActionPlugin logic."""
        from dataclasses import asdict

        resource_data = {k: v for k, v in validated_params.items() if v is not None and k not in self._AUTH_PARAMS and k != "assignment_objects"}
        try:
            resource = self.MODEL_CLASS(**resource_data)
        except TypeError as exc:
            result["failed"] = True
            result["msg"] = str(exc)
            return result

        operation = self._detect_operation(validated_params)
        _lookup_val = getattr(resource, self.LOOKUP_FIELD, None)

        _strip = self._ANSIBLE_DIRECTIVES | (self._READ_ONLY_FIELDS - {"id"}) | {"changed", "assignment_objects", "assignments"}

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
        result.update(
            {
                "changed": manager_result.get("changed", False),
                "failed": False,
                self.MODULE_NAME: clean,
                # Flat top-level keys kept for backward compatibility with
                # playbooks written against <=2.6.
                # Not spread for delete operations (clean would only have state=absent).
                **(clean if operation != "delete" else {}),
            }
        )
        if operation == "delete":
            result[self.MODULE_NAME]["state"] = "absent"

        return result
