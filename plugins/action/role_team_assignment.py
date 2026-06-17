#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.role_team_assignment import AnsibleRoleTeamAssignment

# Maps the suffix of a role definition's content_type to the canonical
# endpoint key used in _SERVICE_LOOKUP_PATH_MAP for type validation.
# e.g. "eda.activation" → suffix "activation" → endpoint key "activations"
_CONTENT_TYPE_ENDPOINT_MAP = {
    "organization": "organizations",
    "team": "teams",
    # Controller (awx)
    "project": "projects",
    "inventory": "inventories",
    "credential": "credentials",
    "jobtemplate": "job_templates",
    "workflowjobtemplate": "workflow_job_templates",
    "executionenvironment": "execution_environments",
    "instancegroup": "instance_groups",
    "notificationtemplate": "notification_templates",
    # EDA
    "activation": "activations",
    "edacredential": "eda_credentials",
    "eventstream": "event_streams",
    "decisionenvironment": "decision_environments",
    # Hub (galaxy)
    "namespace": "namespaces",
    "collectionremote": "collection_remotes",
    "ansiblerepository": "ansible_repositories",
    "containernamespace": "container_namespaces",
    "containerrepository": "container_repositories",
}

# Maps user-facing type names in assignment_objects to the full API path
# used for name-based resource lookup.
#
# Gateway resources are short names — _build_url prepends /api/gateway/v1/.
# EDA and Hub resources require full paths; the Gateway does NOT proxy them
# under /gateway/v1/.
#
# Confirmed via spike (ACA-6324) on AAP 2.7:
#   EDA: GET /api/eda/v1/activations/       → 200  ✓
#   Hub: GET /api/galaxy/v3/namespaces/     → 200  ✓  (NOT /api/hub/v3/)
#
# Controller paths (/api/controller/v2/) — listed but unverified in CI.
# Hub paths confirmed to use /api/galaxy/v3/ prefix.
_SERVICE_LOOKUP_PATH_MAP = {
    # Gateway — short names, auto-prefixed by _build_url
    "organizations": "organizations",
    "teams": "teams",
    # EDA — full path required, confirmed working
    "activations": "/api/eda/v1/activations/",
    "eda_credentials": "/api/eda/v1/eda-credentials/",
    "event_streams": "/api/eda/v1/event-streams/",
    "decision_environments": "/api/eda/v1/decision-environments/",
    # Controller — full path required, add as verified in CI
    "projects": "/api/controller/v2/projects/",
    "inventories": "/api/controller/v2/inventories/",
    "credentials": "/api/controller/v2/credentials/",
    "job_templates": "/api/controller/v2/job_templates/",
    "workflow_job_templates": "/api/controller/v2/workflow_job_templates/",
    "execution_environments": "/api/controller/v2/execution_environments/",
    "instance_groups": "/api/controller/v2/instance_groups/",
    "notification_templates": "/api/controller/v2/notification_templates/",
    # Hub — full path required, confirmed prefix is /api/galaxy/v3/ not /api/hub/v3/
    "namespaces": "/api/galaxy/v3/namespaces/",
    "collection_remotes": "/api/galaxy/v3/remotes/",
    "ansible_repositories": "/api/galaxy/v3/ansible/repositories/",
    "container_namespaces": "/api/galaxy/v3/container-namespaces/",
    "container_repositories": "/api/galaxy/v3/container/repositories/",
}


def _get_expected_endpoint(content_type):
    """Derive the canonical endpoint key from a role definition's content_type.

    Examples:
        "eda.activation"   → "activations"
        "awx.project"      → "projects"
        "shared.organization" → "organizations"
    """
    raw = (content_type or "").strip()
    if not raw:
        return None
    suffix = raw.split(".")[-1] if "." in raw else raw
    return _CONTENT_TYPE_ENDPOINT_MAP.get(suffix, "{0}s".format(suffix))


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "role_team_assignment"
    MODEL_CLASS = AnsibleRoleTeamAssignment
    LOOKUP_FIELD = "id"

    def _resolve_fks_to_strings(self, manager, data_dict):
        """Helper to safely resolve and cast foreign keys."""
        if "role_definition" in data_dict:
            if not str(data_dict["role_definition"]).isdigit():
                try:
                    data_dict["role_definition"] = str(manager.lookup_resource_id("role_definitions", "name", data_dict["role_definition"]))
                except Exception:
                    data_dict["role_definition"] = str(data_dict["role_definition"])
            else:
                data_dict["role_definition"] = str(data_dict["role_definition"])

        if "team" in data_dict:
            if not str(data_dict["team"]).isdigit():
                try:
                    data_dict["team"] = str(manager.lookup_resource_id("teams", "name", data_dict["team"]))
                except Exception:
                    data_dict["team"] = str(data_dict["team"])
            else:
                data_dict["team"] = str(data_dict["team"])

        return data_dict

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

            # ---- resolve role_definition content_type for type validation -----
            # Fetched once here so we can validate each assignment_object's type
            # matches what the role expects before making any Gateway API calls.
            role_def_name = validated_params.get("role_definition", "")
            _role_def_obj = None
            try:
                _role_def_obj = manager.execute(
                    operation="find",
                    module_name="role_definition",
                    ansible_data={"name": role_def_name},
                )
            except Exception:
                pass
            _role_content_type = (_role_def_obj or {}).get("content_type") if _role_def_obj else None
            _expected_endpoint = _get_expected_endpoint(_role_content_type)

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
            base_data = self._resolve_fks_to_strings(manager, base_data)

            all_changed = False
            assignments = []

            for obj in assignment_objects_raw:
                per_obj = dict(base_data)

                # Resolve and strict string-cast object identity
                if obj.get("object_id") is not None:
                    per_obj["object_id"] = str(obj["object_id"])
                elif obj.get("object_ansible_id"):
                    per_obj["object_ansible_id"] = str(obj["object_ansible_id"])
                elif obj.get("name") and obj.get("type"):
                    # Validate the user-provided type matches what the role's
                    # content_type expects. Mismatches cause the Gateway to return
                    # 400 because the resolved ID points to the wrong resource type.
                    if _expected_endpoint and obj["type"] != _expected_endpoint:
                        raise AnsibleError(
                            "Role '{role}' has content_type '{ct}' which requires "
                            "type '{expected}' for name-based lookup, but "
                            "assignment_objects specifies type '{provided}'. "
                            "To grant access to all {resource}s within an organization, "
                            "use the organization-scoped variant of this role. "
                            "To target a specific {resource}, use "
                            "type '{expected}' with the resource name.".format(
                                role=role_def_name,
                                ct=_role_content_type or "unknown",
                                expected=_expected_endpoint,
                                provided=obj["type"],
                                resource=_expected_endpoint.rstrip("s"),
                            )
                        )
                    # Route name lookup to the correct service API.
                    # EDA/Hub resources are not exposed under /api/gateway/v1/ —
                    # they require their own service paths. _build_url passes
                    # absolute paths through unchanged.
                    _lookup_path = _SERVICE_LOOKUP_PATH_MAP.get(obj["type"], obj["type"])
                    try:
                        oid = manager.lookup_resource_id(_lookup_path, "name", obj["name"])
                        per_obj["object_id"] = str(oid)  # CRITICAL: Must be string
                    except Exception:
                        per_obj["object_id"] = str(obj["name"])

                if state == "present":
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
                            delete_payload = dict(per_obj)
                            delete_payload["id"] = find_result["id"]
                            manager.execute(operation="delete", module_name=self.MODULE_NAME, ansible_data=delete_payload)
                            all_changed = True
                    except Exception as exc:
                        self._display.vvv("Delete failed: %s" % exc)

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
        resource_data = self._resolve_fks_to_strings(manager, resource_data)

        if "object_id" in resource_data and resource_data["object_id"] is not None:
            resource_data["object_id"] = str(resource_data["object_id"])

        try:
            resource = self.MODEL_CLASS(**resource_data)
        except TypeError as exc:
            result["failed"] = True
            result["msg"] = str(exc)
            return result

        operation = self._detect_operation(validated_params)
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
