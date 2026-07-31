#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.role_team_assignment import AnsibleRoleTeamAssignment

# Maps content_type suffix → endpoint key (used by _get_expected_endpoint).
# "eda.project" is handled separately via _FULL_TYPE_OVERRIDES to avoid
# collision with "awx.project" which shares the same suffix.
_CONTENT_TYPE_ENDPOINT_MAP = {
    "organization": "organizations",
    "team": "teams",
    # Controller
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
    # Hub
    "namespace": "namespaces",
    "collectionremote": "collection_remotes",
    "ansiblerepository": "ansible_repositories",
    "containernamespace": "container_namespaces",
}

# Full content_type overrides for ambiguous suffixes shared across services.
_FULL_TYPE_OVERRIDES = {
    "eda.project": "eda_projects",
    "eda.edacredential": "eda_credentials",
}

# Maps assignment_objects type → API path for name-based resource lookup.
# Gateway resources use short names (auto-prefixed with /api/gateway/v1/).
# All other services require full absolute paths.
_SERVICE_LOOKUP_PATH_MAP = {
    # Gateway
    "organizations": "organizations",
    "teams": "teams",
    # EDA
    "activations": "/api/eda/v1/activations/",
    "eda_credentials": "/api/eda/v1/eda-credentials/",
    "event_streams": "/api/eda/v1/event-streams/",
    "decision_environments": "/api/eda/v1/decision-environments/",
    "eda_projects": "/api/eda/v1/projects/",
    # Controller
    "projects": "/api/controller/v2/projects/",
    "inventories": "/api/controller/v2/inventories/",
    "credentials": "/api/controller/v2/credentials/",
    "job_templates": "/api/controller/v2/job_templates/",
    "workflow_job_templates": "/api/controller/v2/workflow_job_templates/",
    "execution_environments": "/api/controller/v2/execution_environments/",
    "instance_groups": "/api/controller/v2/instance_groups/",
    "notification_templates": "/api/controller/v2/notification_templates/",
    # Hub
    "namespaces": "/api/galaxy/v3/namespaces/",
    "collection_remotes": "/api/galaxy/pulp/api/v3/remotes/",
    "ansible_repositories": "/api/galaxy/pulp/api/v3/repositories/",
    "container_namespaces": "/api/galaxy/pulp/api/v3/pulp_container/namespaces/",
}


def _get_expected_endpoint(content_type):
    """Return the endpoint key for a role definition's content_type.

    Checks _FULL_TYPE_OVERRIDES first for types that share a suffix across
    services (e.g. eda.project vs awx.project), then falls back to suffix lookup.

    Raises ValueError for unknown content types instead of guessing with
    naive pluralisation (e.g. "inventory" → "inventorys" is wrong).
    """
    raw = (content_type or "").strip()
    if not raw:
        return None
    if raw in _FULL_TYPE_OVERRIDES:
        return _FULL_TYPE_OVERRIDES[raw]
    suffix = raw.split(".")[-1] if "." in raw else raw
    if suffix in _CONTENT_TYPE_ENDPOINT_MAP:
        return _CONTENT_TYPE_ENDPOINT_MAP[suffix]
    # Fail-closed: unknown content types are errors, not guesses.
    known = sorted(set(list(_CONTENT_TYPE_ENDPOINT_MAP.keys()) + list(_FULL_TYPE_OVERRIDES.keys())))
    raise ValueError(
        "Unknown content_type '%s' in role definition. "
        "Known suffixes/types: %s. "
        "If this is a new resource type, add it to "
        "_CONTENT_TYPE_ENDPOINT_MAP or _FULL_TYPE_OVERRIDES "
        "in role_team_assignment.py." % (content_type, ", ".join(known))
    )


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "role_team_assignment"
    MODEL_CLASS = AnsibleRoleTeamAssignment
    LOOKUP_FIELD = "id"

    def _resolve_fks_to_strings(self, manager, data_dict):
        """Resolve role_definition and team names to string IDs in-place."""
        if "role_definition" in data_dict:
            if not str(data_dict["role_definition"]).isdigit():
                try:
                    data_dict["role_definition"] = str(manager.lookup_resource_id("role_definitions", "name", data_dict["role_definition"]))
                except Exception as _exc:
                    self._display.warning(
                        "role_team_assignment: could not resolve role_definition %r to an ID (%s). "
                        "Pass the numeric ID directly to skip lookup." % (data_dict["role_definition"], _exc)
                    )
                    data_dict["role_definition"] = str(data_dict["role_definition"])
            else:
                data_dict["role_definition"] = str(data_dict["role_definition"])

        if "team" in data_dict:
            if not str(data_dict["team"]).isdigit():
                try:
                    data_dict["team"] = str(manager.lookup_resource_id("teams", "name", data_dict["team"]))
                except Exception as _exc:
                    self._display.warning(
                        "role_team_assignment: could not resolve team name %r to an ID (%s). "
                        "Pass the team's numeric ID or ansible_id directly to skip lookup." % (data_dict["team"], _exc)
                    )
                    data_dict["team"] = str(data_dict["team"])
            else:
                data_dict["team"] = str(data_dict["team"])

        return data_dict

    def run(self, tmp=None, task_vars=None):
        """Run role_team_assignment.

        Single-object path (object_id / object_ansible_id): delegates to
        _run_standard(). Multi-object path (assignment_objects): iterates,
        resolves name+type to object_id, and manages assignments idempotently.
        """
        if task_vars is None:
            task_vars = {}
        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError("Could not load DOCUMENTATION for %s module" % self.MODULE_NAME)
            validated_input = self._validate_data(self._task.args.copy(), argspec, "input")
            validated_params = validated_input.validated_parameters

            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            state = validated_params.get("state", "present")
            assignment_objects_raw = validated_params.get("assignment_objects") or []

            if not assignment_objects_raw:
                return self._run_standard(result, manager, argspec, validated_params, state)

            # Resolve the role definition's content_type once for type validation.
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

            _skip = self._AUTH_PARAMS | {"assignment_objects", "state", "object_id", "object_ids", "object_ansible_id"}
            base_data = {k: v for k, v in validated_params.items() if v is not None and v != "" and k not in _skip}
            base_data = self._resolve_fks_to_strings(manager, base_data)

            all_changed = False
            assignments = []

            _orig_role_def = validated_params.get("role_definition")
            _orig_team = validated_params.get("team")
            _orig_team_ansible_id = validated_params.get("team_ansible_id")

            def _humanise(result, obj_item):
                """Return a copy of result with original user-supplied names overlaid.

                Creates a shallow copy so the original dict (which may be cached
                or shared by the manager internals) is not mutated.
                """
                humanised = dict(result)  # shallow copy — safe for flat dicts
                if _orig_role_def:
                    humanised["role_definition"] = _orig_role_def
                if _orig_team:
                    humanised["team"] = _orig_team
                elif _orig_team_ansible_id:
                    humanised["team_ansible_id"] = _orig_team_ansible_id
                if obj_item and obj_item.get("name"):
                    humanised["object_name"] = obj_item["name"]
                    humanised["object_type"] = obj_item.get("type")
                return humanised

            for obj in assignment_objects_raw:
                per_obj = dict(base_data)

                if obj.get("object_id") is not None:
                    per_obj["object_id"] = str(obj["object_id"])
                elif obj.get("object_ansible_id"):
                    per_obj["object_ansible_id"] = str(obj["object_ansible_id"])
                elif obj.get("name") and obj.get("type"):
                    if _expected_endpoint and obj["type"] != _expected_endpoint:
                        raise AnsibleError(
                            "Role '{role}' has content_type '{ct}' which requires type '{expected}' in assignment_objects, but got '{provided}'.".format(
                                role=role_def_name,
                                ct=_role_content_type or "unknown",
                                expected=_expected_endpoint,
                                provided=obj["type"],
                            )
                        )
                    _lookup_path = _SERVICE_LOOKUP_PATH_MAP.get(obj["type"], obj["type"])
                    try:
                        if _lookup_path.startswith("/api/") and not _lookup_path.startswith("/api/gateway/"):
                            # Service-specific path (EDA/Hub): use search_api
                            # which accepts full paths, bypassing the Gateway prefix
                            # that lookup_resource_id would hardcode.
                            _search = manager.search_api(_lookup_path, query_params={"name": obj["name"]})
                            # Hub endpoints by default have results present in data field instead
                            _results = _search.get("results", _search.get("data", []))
                            if not _results:
                                raise ValueError("Resource '%s' with name=%s not found at %s" % (obj["type"], obj["name"], _lookup_path))
                            if "id" in _results[0]:
                                oid = _results[0].get("id")
                            elif "prn" in _results[0]:
                                oid = _results[0].get("prn").split(":")[-1]
                            else:
                                raise ValueError("Resource '%s' at %s returned no 'id' field" % (obj["name"], _lookup_path))
                        else:
                            # Gateway-native endpoint: use standard lookup
                            oid = manager.lookup_resource_id(_lookup_path, "name", obj["name"])
                        per_obj["object_id"] = str(oid)
                    except Exception:
                        self._display.warning(
                            "Could not resolve %s '%s' via endpoint '%s'. "
                            "Passing raw name to the API — the request may fail. "
                            "Verify the resource exists and is accessible with "
                            "current credentials." % (obj["type"], obj["name"], _lookup_path)
                        )
                        per_obj["object_id"] = str(obj["name"])

                if state == "present":
                    try:
                        find_result = manager.execute(operation="find", module_name=self.MODULE_NAME, ansible_data=per_obj)
                        if find_result and find_result.get("id"):
                            assignments.append(_humanise(find_result, obj))
                            continue
                    except Exception:
                        pass
                    mgr_result = manager.execute(operation="create", module_name=self.MODULE_NAME, ansible_data=per_obj)
                    all_changed = True
                    assignments.append(_humanise(mgr_result, obj))

                elif state == "absent":
                    try:
                        find_result = manager.execute(operation="find", module_name=self.MODULE_NAME, ansible_data=per_obj)
                        if find_result and find_result.get("id"):
                            delete_payload = dict(per_obj)
                            delete_payload["id"] = find_result["id"]
                            manager.execute(operation="delete", module_name=self.MODULE_NAME, ansible_data=delete_payload)
                            all_changed = True
                            assignments.append(_humanise(find_result, obj))
                    except Exception as exc:
                        self._display.vvv("Delete failed: %s" % exc)

                elif state == "exists":
                    try:
                        find_result = manager.execute(operation="find", module_name=self.MODULE_NAME, ansible_data=per_obj)
                        if find_result and find_result.get("id"):
                            assignments.append(_humanise(find_result, obj))
                    except Exception:
                        pass

            if state == "exists" and not assignments:
                raise ValueError("No %s found matching the given criteria" % self.MODULE_NAME)

            _strip = self._ANSIBLE_DIRECTIVES | (self._READ_ONLY_FIELDS - {"id"}) | {"changed", "assignment_objects", "assignments"}
            primary = assignments[0] if assignments else {}
            clean = {k: v for k, v in primary.items() if k not in _strip}

            result.update(
                {
                    "changed": all_changed,
                    "failed": False,
                    self.MODULE_NAME: clean,
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

    def _run_standard(self, result, manager, argspec, validated_params, state):
        """Single-object path: mirrors the standard BaseResourceActionPlugin logic."""
        from dataclasses import asdict

        resource_data = {k: v for k, v in validated_params.items() if v is not None and v != "" and k not in self._AUTH_PARAMS and k != "assignment_objects"}
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
                find_result = manager.execute(operation="find", module_name=self.MODULE_NAME, ansible_data=resource_data)
                if find_result and find_result.get("id"):
                    if not self._should_update(resource_data, find_result):
                        clean = {k: v for k, v in find_result.items() if k not in _strip}
                        result.update({"changed": False, "failed": False, self.MODULE_NAME: clean, **clean})
                        return result
                    operation = "update"
                    resource.id = find_result["id"]
            except Exception:
                pass

        if operation == "delete" and not getattr(resource, "id", None):
            try:
                find_result = manager.execute(operation="find", module_name=self.MODULE_NAME, ansible_data=resource_data)
                if find_result and find_result.get("id"):
                    resource.id = find_result["id"]
                else:
                    result.update({"changed": False, "failed": False, self.MODULE_NAME: {"state": "absent"}})
                    return result
            except Exception:
                result.update({"changed": False, "failed": False, self.MODULE_NAME: {"state": "absent"}})
                return result

        ansible_data = asdict(resource)
        manager_result = manager.execute(operation=operation, module_name=self.MODULE_NAME, ansible_data=ansible_data)

        clean = {k: v for k, v in manager_result.items() if k not in _strip}
        result.update(
            {
                "changed": manager_result.get("changed", False),
                "failed": False,
                self.MODULE_NAME: clean,
                **(clean if operation != "delete" else {}),
            }
        )
        if operation == "delete":
            result[self.MODULE_NAME]["state"] = "absent"

        return result
