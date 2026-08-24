#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.role_team_assignment import AnsibleRoleTeamAssignment

_CONTENT_TYPE_ENDPOINT_MAP = {
    "organization": "organizations",
    "team": "teams",
    "project": "projects",
    "inventory": "inventories",
    "credential": "credentials",
    "jobtemplate": "job_templates",
    "workflowjobtemplate": "workflow_job_templates",
    "executionenvironment": "execution_environments",
    "instancegroup": "instance_groups",
    "notificationtemplate": "notification_templates",
    "activation": "activations",
    "edacredential": "eda_credentials",
    "eventstream": "event_streams",
    "decisionenvironment": "decision_environments",
    "namespace": "namespaces",
    "collectionremote": "collection_remotes",
    "ansiblerepository": "ansible_repositories",
    "containernamespace": "container_namespaces",
}

_FULL_TYPE_OVERRIDES = {
    "eda.project": "eda_projects",
    "eda.edacredential": "eda_credentials",
}

_SERVICE_LOOKUP_PATH_MAP = {
    "organizations": "organizations",
    "teams": "teams",
    "activations": "/api/eda/v1/activations/",
    "eda_credentials": "/api/eda/v1/eda-credentials/",
    "event_streams": "/api/eda/v1/event-streams/",
    "decision_environments": "/api/eda/v1/decision-environments/",
    "eda_projects": "/api/eda/v1/projects/",
    "projects": "/api/controller/v2/projects/",
    "inventories": "/api/controller/v2/inventories/",
    "credentials": "/api/controller/v2/credentials/",
    "job_templates": "/api/controller/v2/job_templates/",
    "workflow_job_templates": "/api/controller/v2/workflow_job_templates/",
    "execution_environments": "/api/controller/v2/execution_environments/",
    "instance_groups": "/api/controller/v2/instance_groups/",
    "notification_templates": "/api/controller/v2/notification_templates/",
    "namespaces": "/api/galaxy/v3/namespaces/",
    "collection_remotes": "/api/galaxy/pulp/api/v3/remotes/",
    "ansible_repositories": "/api/galaxy/pulp/api/v3/repositories/",
    "container_namespaces": "/api/galaxy/pulp/api/v3/pulp_container/namespaces/",
}

_CONTROLLER_NON_ORG_TYPES = frozenset(
    {
        "execution_environments",
        "instance_groups",
    }
)
_GATEWAY_ORG_TYPES = frozenset({"teams"})


def _get_expected_endpoint(content_type):
    raw = (content_type or "").strip()
    if not raw:
        return None
    if raw in _FULL_TYPE_OVERRIDES:
        return _FULL_TYPE_OVERRIDES[raw]
    suffix = raw.split(".")[-1] if "." in raw else raw
    if suffix in _CONTENT_TYPE_ENDPOINT_MAP:
        return _CONTENT_TYPE_ENDPOINT_MAP[suffix]
    known = sorted(set(list(_CONTENT_TYPE_ENDPOINT_MAP.keys()) + list(_FULL_TYPE_OVERRIDES.keys())))
    raise ValueError(
        "Unknown content_type '%s' in role definition. Known suffixes/types: %s. "
        "If this is a new resource type, add it to _CONTENT_TYPE_ENDPOINT_MAP or "
        "_FULL_TYPE_OVERRIDES in role_team_assignment.py." % (content_type, ", ".join(known))
    )


def _service_kind(obj_type):
    path = _SERVICE_LOOKUP_PATH_MAP.get(obj_type, obj_type)
    if isinstance(path, str) and path.startswith("/api/controller/"):
        return "controller"
    if isinstance(path, str) and path.startswith("/api/eda/"):
        return "eda"
    if isinstance(path, str) and path.startswith("/api/galaxy/"):
        return "hub"
    return "gateway"


def _result_id(item, name, lookup_path):
    if "id" in item:
        return item["id"]
    if "prn" in item:
        return str(item["prn"]).rsplit(":", maxsplit=1)[-1]
    raise ValueError("Resource '%s' at %s returned no 'id' field" % (name, lookup_path))


def _search_results(payload):
    return payload.get("results", payload.get("data", [])) or []


def _matches_org(item, org_id):
    for key in ("organization_id", "organization"):
        val = item.get(key)
        if val is None:
            continue
        if isinstance(val, dict):
            val = val.get("id")
        if str(val) == str(org_id):
            return True
    return False


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "role_team_assignment"
    MODEL_CLASS = AnsibleRoleTeamAssignment
    LOOKUP_FIELD = "id"

    def _resolve_fks_to_strings(self, manager, data_dict):
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

    def _resolve_organization_id(self, manager, organization, service):
        if service == "controller":
            payload = manager.search_api("/api/controller/v2/organizations/", query_params={"name": organization})
        elif service == "eda":
            payload = manager.search_api("/api/eda/v1/organizations/", query_params={"name": organization})
        else:
            return manager.lookup_resource_id("organizations", "name", organization)

        results = _search_results(payload)
        if len(results) != 1:
            raise AnsibleError("Expected exactly one organization named '%s' on %s, got %s" % (organization, service, len(results)))
        return _result_id(results[0], organization, "organizations")

    def _resolve_named_object_id(self, manager, obj):
        obj_type = obj["type"]
        name = obj["name"]
        organization = obj.get("organization")
        lookup_path = _SERVICE_LOOKUP_PATH_MAP.get(obj_type, obj_type)
        service = _service_kind(obj_type)

        if organization:
            if service == "hub":
                raise AnsibleError("organization is not supported for Hub types such as '%s'" % obj_type)
            if service == "controller" and obj_type in _CONTROLLER_NON_ORG_TYPES:
                raise AnsibleError(
                    "organization is not supported for Controller type such as '%s'" % obj_type
                )
            if service == "gateway" and obj_type not in _GATEWAY_ORG_TYPES:
                raise AnsibleError("organization is only supported for Gateway type 'teams' (got '%s')" % obj_type)

        org_id = None
        if organization:
            org_id = self._resolve_organization_id(manager, organization, service)

        query = {"name": name}
        if org_id is not None and service == "controller":
            query["organization"] = org_id
        if org_id is not None and service == "gateway" and obj_type == "teams":
            query["organization"] = org_id

        if isinstance(lookup_path, str) and lookup_path.startswith("/api/") and not lookup_path.startswith("/api/gateway/"):
            payload = manager.search_api(lookup_path, query_params=query)
            results = _search_results(payload)
            if service == "eda" and org_id is not None:
                results = [r for r in results if _matches_org(r, org_id)]
            if len(results) != 1:
                raise ValueError(
                    "Expected exactly one %s named '%s'%s at %s, got %s"
                    % (
                        obj_type,
                        name,
                        (" in organization '%s'" % organization) if organization else "",
                        lookup_path,
                        len(results),
                    )
                )
            return str(_result_id(results[0], name, lookup_path))

        if org_id is not None and obj_type == "teams":
            payload = manager.search_api("teams", query_params=query)
            results = _search_results(payload)
            results = [r for r in results if _matches_org(r, org_id)]
            if len(results) != 1:
                raise ValueError("Expected exactly one team named '%s' in organization '%s', got %s" % (name, organization, len(results)))
            return str(_result_id(results[0], name, "teams"))

        return str(manager.lookup_resource_id(lookup_path, "name", name))

    def run(self, tmp=None, task_vars=None):
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

            _skip = self._AUTH_PARAMS | {"assignment_objects", "state", "object_id", "object_ansible_id"}
            base_data = {k: v for k, v in validated_params.items() if v is not None and v != "" and k not in _skip}
            base_data = self._resolve_fks_to_strings(manager, base_data)

            all_changed = False
            assignments = []

            _orig_role_def = validated_params.get("role_definition")
            _orig_team = validated_params.get("team")
            _orig_team_ansible_id = validated_params.get("team_ansible_id")

            def _humanise(api_result, obj_item):
                humanised = dict(api_result)
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
                    try:
                        per_obj["object_id"] = self._resolve_named_object_id(manager, obj)
                    except AnsibleError:
                        raise
                    except Exception as exc:
                        raise AnsibleError(
                            "Could not resolve %s '%s'%s: %s"
                            % (
                                obj["type"],
                                obj["name"],
                                (" (organization=%s)" % obj["organization"]) if obj.get("organization") else "",
                                exc,
                            )
                        ) from exc

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
