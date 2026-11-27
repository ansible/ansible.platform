#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.export.

Exports Controller and Gateway resources using one manager connection.
Resolves FK IDs to names via a pre-built cache and fetches related objects
(associations, survey_spec) via sub-endpoint queries.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import traceback as _tb

import yaml
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError
from ansible_collections.ansible.platform.plugins.plugin_utils.workflow_export import (
    export_workflow_nodes,
    read_named_workflow_dependency,
    workflow_organization_name,
)

CONTROLLER_ORGANIZATION_ENDPOINT = "api/controller/v2/organizations/"
GATEWAY_ORGANIZATION_ENDPOINT = "api/gateway/v1/organizations/"
ROLE_DEFINITION_ENDPOINT = "api/gateway/v1/role_definitions/"

# Resource types and their API endpoints (in export order).
# Gateway resources (orgs, users, teams) use api/gateway/v1/.
# Controller resources use api/controller/v2/.
EXPORTABLE_RESOURCES = [
    ("organizations", "api/gateway/v1/organizations/", "name"),
    ("controller_organizations", CONTROLLER_ORGANIZATION_ENDPOINT, "name"),
    ("users", "api/gateway/v1/users/", "username"),
    ("teams", "api/gateway/v1/teams/", "name"),
    ("authenticators", "api/gateway/v1/authenticators/", "name"),
    ("authenticator_maps", "api/gateway/v1/authenticator_maps/", "name"),
    ("tokens", "api/gateway/v1/tokens/", "id"),
    ("role_definitions", ROLE_DEFINITION_ENDPOINT, "name"),
    ("credential_types", "api/controller/v2/credential_types/", "name"),
    ("credentials", "api/controller/v2/credentials/", "name"),
    ("execution_environments", "api/controller/v2/execution_environments/", "name"),
    ("instance_groups", "api/controller/v2/instance_groups/", "name"),
    ("notification_templates", "api/controller/v2/notification_templates/", "name"),
    ("projects", "api/controller/v2/projects/", "name"),
    ("labels", "api/controller/v2/labels/", "name"),
    ("inventory", "api/controller/v2/inventories/", "name"),
    ("inventory_sources", "api/controller/v2/inventory_sources/", "name"),
    ("job_templates", "api/controller/v2/job_templates/", "name"),
    ("workflow_job_templates", "api/controller/v2/workflow_job_templates/", "name"),
    ("schedules", "api/controller/v2/schedules/", "name"),
    ("role_user_assignments", "api/gateway/v1/role_user_assignments/", "id"),
    ("role_team_assignments", "api/gateway/v1/role_team_assignments/", "id"),
]
GATEWAY_RESOURCE_TYPES = frozenset(
    {"organizations", "users", "teams", "authenticators", "authenticator_maps", "tokens", "role_user_assignments", "role_team_assignments"}
)

MANAGED_CREDENTIAL_NAMES = frozenset({"Ansible Galaxy"})
MANAGED_EXECUTION_ENVIRONMENT_NAMES = frozenset(
    {
        "Control Plane Execution Environment",
        "Default execution environment",
        "Minimal execution environment",
        "Hub Default execution environment",
        "Hub Minimal execution environment",
    }
)

ROLE_OBJECT_TYPE_MAP = {
    ("shared", "organization"): ("organizations", "api/gateway/v1/organizations/"),
    ("shared", "team"): ("teams", "api/gateway/v1/teams/"),
    ("gateway", "organization"): ("organizations", "api/gateway/v1/organizations/"),
    ("gateway", "team"): ("teams", "api/gateway/v1/teams/"),
    ("awx", "project"): ("awx.project", "api/controller/v2/projects/"),
    ("awx", "inventory"): ("awx.inventory", "api/controller/v2/inventories/"),
    ("awx", "credential"): ("awx.credential", "api/controller/v2/credentials/"),
    ("awx", "jobtemplate"): ("awx.jobtemplate", "api/controller/v2/job_templates/"),
    ("awx", "workflowjobtemplate"): ("awx.workflowjobtemplate", "api/controller/v2/workflow_job_templates/"),
    ("awx", "executionenvironment"): ("awx.executionenvironment", "api/controller/v2/execution_environments/"),
    ("awx", "instancegroup"): ("awx.instancegroup", "api/controller/v2/instance_groups/"),
    ("awx", "notificationtemplate"): ("awx.notificationtemplate", "api/controller/v2/notification_templates/"),
}

# FK fields and the endpoint to resolve them against.
# (field_name, api_endpoint, identifier_field)
FK_RESOLUTION_MAP = {
    # Controller resources store Controller organization IDs. Gateway teams and
    # user organization_ids are resolved separately through Gateway below.
    "organization": (CONTROLLER_ORGANIZATION_ENDPOINT, "name"),
    "authenticator": ("api/gateway/v1/authenticators/", "name"),
    "role_definition": (ROLE_DEFINITION_ENDPOINT, "name"),
    "role": (ROLE_DEFINITION_ENDPOINT, "name"),
    "inventory": ("api/controller/v2/inventories/", "name"),
    "project": ("api/controller/v2/projects/", "name"),
    "credential_type": ("api/controller/v2/credential_types/", "name"),
    "execution_environment": ("api/controller/v2/execution_environments/", "name"),
    "source_project": ("api/controller/v2/projects/", "name"),
    "default_environment": ("api/controller/v2/execution_environments/", "name"),
    "user": ("api/gateway/v1/users/", "username"),
    "team": ("api/gateway/v1/teams/", "name"),
    "credential": ("api/controller/v2/credentials/", "name"),
    "webhook_credential": ("api/controller/v2/credentials/", "name"),
    "insights_credential": ("api/controller/v2/credentials/", "name"),
    "vault_credential": ("api/controller/v2/credentials/", "name"),
    "signature_validation_credential": ("api/controller/v2/credentials/", "name"),
    "unified_job_template": ("api/controller/v2/unified_job_templates/", "name"),
}

# Fields to strip from exported resources (read-only / internal / computed).
# Comprehensive list covering Controller and Gateway API response fields
# that are not valid module parameters.
STRIP_FIELDS = frozenset(
    {
        # Core metadata
        "id",
        "type",
        "url",
        "related",
        "summary_fields",
        "created",
        "modified",
        "created_by",
        "modified_by",
        "user_capabilities",
        "object_roles",
        # Controller project sync output; it is not a project module option.
        "scm_revision",
        # Inventory computed fields
        "has_active_failures",
        "has_inventory_sources",
        "hosts_with_active_failures",
        "inventory_sources_with_failures",
        "total_groups",
        "total_hosts",
        "total_inventory_sources",
        "pending_deletion",
        # Job/launch computed fields
        "last_job_run",
        "last_job_failed",
        "next_job_run",
        "status",
        "last_update_failed",
        "last_updated",
        "last_job_host_summary",
        "next_schedule",
        "last_login",
        "last_login_from",
        "last_login_results",
        "dtstart",
        "dtend",
        "next_run",
        "timezone",
        "until",
        "capacity",
        "consumed_capacity",
        "percent_capacity_remaining",
        "jobs_running",
        "jobs_total",
        "instances",
        "sso_login_url",
        # Credential type internal fields
        "managed",
        "namespace",
        # Project computed fields
        "current_job",
        "current_update",
        "last_update",
        "custom_virtualenv",
        "last_job",
        # Organization computed fields
        # General computed/internal
        "opa_query_path",
        "launch_type",
        "is_sliced_job",
        "unified_job_type",
        "elapsed",
        "artifacts",
        "job_args",
        "job_cwd",
        "job_env",
        "result_stdout",
        "result_traceback",
        "event_processing_finished",
        "started",
        "finished",
        "canceled_on",
    }
)

# ``type`` is normally API metadata, but authenticators use it as the
# required plugin discriminator accepted by the authenticator module.
RESOURCE_FIELDS_TO_PRESERVE = {
    "authenticators": frozenset({"type"}),
    "controller_organizations": frozenset({"opa_query_path"}),
}

# Association sub-endpoints to fetch per resource type.
# (export_key, sub_endpoint_suffix, mode)
# mode: "names" = extract name list, "dict" = include raw dict
RESOURCE_ASSOCIATIONS = {
    "job_templates": [
        ("credentials", "credentials/", "names"),
        ("labels", "labels/", "names"),
        ("instance_groups", "instance_groups/", "names"),
        ("notification_templates_started", "notification_templates_started/", "names"),
        ("notification_templates_success", "notification_templates_success/", "names"),
        ("notification_templates_error", "notification_templates_error/", "names"),
        ("survey_spec", "survey_spec/", "dict"),
    ],
    "workflow_job_templates": [
        ("labels", "labels/", "names"),
        ("notification_templates_started", "notification_templates_started/", "names"),
        ("notification_templates_success", "notification_templates_success/", "names"),
        ("notification_templates_error", "notification_templates_error/", "names"),
        ("survey_spec", "survey_spec/", "dict"),
    ],
    "projects": [
        ("notification_templates_started", "notification_templates_started/", "names"),
        ("notification_templates_success", "notification_templates_success/", "names"),
        ("notification_templates_error", "notification_templates_error/", "names"),
    ],
    "inventory_sources": [
        ("notification_templates_started", "notification_templates_started/", "names"),
        ("notification_templates_success", "notification_templates_success/", "names"),
        ("notification_templates_error", "notification_templates_error/", "names"),
    ],
    "group": [
        ("hosts", "hosts/", "names"),
        ("children", "children/", "names"),
    ],
    "controller_organizations": [
        ("galaxy_credentials", "galaxy_credentials/", "names"),
        ("instance_groups", "instance_groups/", "names"),
    ],
    "credentials": [
        ("user", "owner_users/", "names_or_usernames"),
        ("team", "owner_teams/", "names_or_usernames"),
    ],
    "schedules": [
        ("credentials", "credentials/", "names"),
        ("labels", "labels/", "names"),
        ("instance_groups", "instance_groups/", "names"),
    ],
}

# Association sub-endpoints to fetch per resource type (inventory children).
RESOURCE_ASSOCIATIONS_INVENTORY = [
    ("hosts", "hosts/", "objects"),
    ("groups", "groups/", "objects"),
]

# Fields to keep when exporting hosts/groups as inline objects.
HOST_EXPORT_FIELDS = {"name", "description", "enabled", "instance_id", "variables"}
GROUP_EXPORT_FIELDS = {"name", "description", "variables"}


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "export"
    _RESOURCE_NORMALIZERS = {"projects": "_normalize_project"}

    @staticmethod
    def _contains_masked_secret(value):
        """Return true when an object contains an API-masked secret sentinel."""
        if isinstance(value, str):
            return value == "$encrypted$"
        if isinstance(value, dict):
            return any(ActionModule._contains_masked_secret(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(ActionModule._contains_masked_secret(item) for item in value)
        return False

    def run(self, tmp=None, task_vars=None):
        """Export resources from the platform."""
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            export_all = validated_params.get("all", False)
            all_requested = export_all

            # Build FK name cache
            self._display.vvv("Building FK name resolution cache...")
            max_objects = validated_params.get("max_objects", 10000)
            if max_objects < 1:
                raise ValueError("max_objects must be greater than zero")
            selected = {name for name, _, _ in EXPORTABLE_RESOURCES if validated_params.get(name) is not None}
            name_cache = {} if not all_requested and selected == {"workflow_job_templates"} else self._build_name_cache(manager, max_objects)

            assets = {}
            non_restorable = {"tokens": [], "authenticators": [], "authenticator_maps": [], "credentials": [], "notification_templates": []}
            self._non_restorable_role_assignments = []
            for res_type, endpoint, id_field in EXPORTABLE_RESOURCES:
                filter_values = validated_params.get(res_type)

                if not all_requested and filter_values is None:
                    continue

                should_export_all = all_requested or filter_values == ["all"]
                names_filter = None if should_export_all else filter_values

                self._display.vvv("Exporting %s..." % res_type)
                if res_type == "tokens":
                    exported = self._export_resource_type(manager, res_type, endpoint, id_field, name_cache, names_filter, max_objects)
                    non_restorable["tokens"].extend(exported)
                    continue
                if res_type in ("role_user_assignments", "role_team_assignments"):
                    exported = self._export_role_assignments(manager, res_type, endpoint, names_filter, name_cache, max_objects)
                    if self._non_restorable_role_assignments:
                        non_restorable.setdefault(res_type, []).extend(self._non_restorable_role_assignments)
                        self._non_restorable_role_assignments = []
                else:
                    exported = self._export_resource_type(manager, res_type, endpoint, id_field, name_cache, names_filter, max_objects)
                if res_type == "workflow_job_templates":
                    incomplete = [item for item in exported if "non_restorable_reason" in item]
                    if incomplete:
                        non_restorable[res_type] = incomplete
                        exported = [item for item in exported if "non_restorable_reason" not in item]
                if res_type in ("authenticators", "credentials", "notification_templates"):
                    restorable = []
                    field = {"authenticators": "configuration", "credentials": "inputs", "notification_templates": "notification_configuration"}[res_type]
                    for item in exported:
                        if self._contains_masked_secret(item.get(field)):
                            non_restorable[res_type].append(item)
                        else:
                            restorable.append(item)
                    exported = restorable
                if exported:
                    assets[res_type] = exported

            if "authenticator_maps" in assets:
                # A map is restorable when its authenticator is included in
                # this export or intentionally supplied by the target. A
                # masked authenticator makes its map non-restorable.
                masked_authenticators = {item.get("name") for item in non_restorable.get("authenticators", [])}
                kept_maps = []
                for item in assets["authenticator_maps"]:
                    authenticator_name = item.get("authenticator")
                    if authenticator_name in masked_authenticators:
                        non_restorable["authenticator_maps"].append(item)
                    else:
                        kept_maps.append(item)
                if kept_maps:
                    assets["authenticator_maps"] = kept_maps
                else:
                    assets.pop("authenticator_maps", None)

            non_restorable = {key: value for key, value in non_restorable.items() if value}
            result["changed"] = False
            result["failed"] = False
            result["assets"] = assets
            if non_restorable:
                result["non_restorable"] = non_restorable

        except Exception as exc:
            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result

    def _build_name_cache(self, manager, max_objects):
        """Pre-fetch all resource types and build {endpoint: {id: name}} cache."""
        cache = {}
        # Deduplicate endpoints from FK_RESOLUTION_MAP
        endpoints = set()
        for endpoint, id_field in FK_RESOLUTION_MAP.values():
            endpoints.add((endpoint, id_field))
        # Gateway owns team organization IDs and user organization_ids, while
        # Controller resources use the Controller organization ID space.
        endpoints.add((GATEWAY_ORGANIZATION_ENDPOINT, "name"))

        for endpoint, id_field in endpoints:
            try:
                response = manager.search_api(
                    endpoint=endpoint,
                    return_all=True,
                    max_objects=max_objects,
                )
                results = response.get("results", [])
                cache[endpoint] = {r["id"]: r.get(id_field, r.get("name", r.get("username", str(r["id"])))) for r in results if "id" in r}
                if endpoint == "api/controller/v2/inventories/":
                    cache[endpoint + ":organizations"] = {r["id"]: r.get("organization") for r in results if "id" in r}
                self._display.vvvv("Cached %d entries for %s" % (len(cache[endpoint]), endpoint))
            except Exception as exc:
                self._display.warning("Failed to cache %s: %s" % (endpoint, exc))
                raise

        return cache

    def _resolve_fk(self, field_name, value, name_cache, endpoint_override=None):
        """Resolve an FK integer ID to a resource name using the cache."""
        if value is None or not isinstance(value, int):
            return value

        fk_info = FK_RESOLUTION_MAP.get(field_name)
        if not fk_info:
            return value

        endpoint = endpoint_override or fk_info[0]
        endpoint_cache = name_cache.get(endpoint, {})
        resolved = endpoint_cache.get(value)
        if resolved is not None:
            return resolved

        self._display.vvvv("FK cache miss: %s=%d" % (field_name, value))
        return value

    def _search_resources(self, manager, endpoint, id_field, names_filter, max_objects):
        """Search by lookup-field value, numeric ID, or qualified named URL.

        Resolve named URLs through the SDK before querying by ID, rather than
        treating them as literal names. Avoid Controller-only ``or__`` filters.
        """
        if names_filter is None:
            return manager.search_api(endpoint=endpoint, return_all=True, max_objects=max_objects)
        if not names_filter:
            return {"results": []}

        results = []
        seen_ids = set()
        for reference in names_filter:
            query_field = id_field
            query_value = reference
            if str(reference).isdecimal():
                query_field, query_value = "id", int(reference)
            elif "++" in str(reference):
                service = "gateway" if "/gateway/" in endpoint else "controller"
                resource_type = endpoint.strip("/").rsplit("/", 1)[-1]
                query_field = "id"
                query_value = manager.lookup_resource_id(resource_type, id_field, reference, service=service)
            response = manager.search_api(
                endpoint=endpoint,
                query_params={query_field: query_value},
                return_all=True,
                max_objects=max_objects,
            )
            for resource in response.get("results", []):
                resource_id = resource.get("id")
                identity = ("id", resource_id) if resource_id is not None else ("resource", repr(sorted(resource.items())))
                if identity not in seen_ids:
                    seen_ids.add(identity)
                    results.append(resource)
                    if len(results) > max_objects:
                        raise ValueError("Endpoint '%s' returned more than max_objects=%d objects" % (endpoint, max_objects))

        return {"results": results}

    def _export_role_assignments(self, manager, res_type, endpoint, names_filter, name_cache, max_objects):
        """Export assignments using portable role/object names."""
        response = self._search_resources(manager, endpoint, "id", names_filter, max_objects)
        exported = []
        assignments = [assignment for assignment in response.get("results", []) if isinstance(assignment, dict)]
        role_definition_cache, object_cache = self._build_role_assignment_export_cache(manager, assignments, max_objects)
        for assignment in assignments:
            summary = assignment.get("summary_fields", {})
            role = summary.get("role_definition", {})
            user = summary.get("user", {})
            team = summary.get("team", {})
            content = summary.get("content_object", {})
            service = content.get("service")
            model = content.get("model_name")
            role_content_type = role.get("content_type")
            role_id = role.get("id")
            if not role_content_type and role_id is not None:
                role_content_type = role_definition_cache.get(str(role_id), {}).get("content_type")
            if not (service and model) and isinstance(role_content_type, str) and "." in role_content_type:
                service, model = role_content_type.split(".", 1)
            object_type_path = ROLE_OBJECT_TYPE_MAP.get((service, model))
            item = {
                "role_definition": role.get("name", assignment.get("role_definition")),
            }
            if res_type == "role_user_assignments":
                item["user"] = user.get("username", assignment.get("user"))
            else:
                team_name = team.get("name", assignment.get("team"))
                item["team"] = team_name
                team_org_id = team.get("organization")
                if isinstance(team_org_id, int):
                    team_org = name_cache.get(GATEWAY_ORGANIZATION_ENDPOINT, {}).get(team_org_id)
                    if team_org:
                        item["team_organization"] = team_org
            object_id = assignment.get("object_id") or content.get("pk") or content.get("id")
            object_ansible_id = assignment.get("object_ansible_id")
            if object_type_path and (object_id is not None or object_ansible_id):
                object_type, object_endpoint = object_type_path
                cached_objects = object_cache[object_endpoint]
                detail = cached_objects["by_id"].get(str(object_id)) if object_id is not None else cached_objects["by_ansible_id"].get(str(object_ansible_id))
                if isinstance(detail, dict) and detail.get("name"):
                    object_data = {"name": detail["name"], "type": object_type}
                    if object_type == "awx.credential":
                        credential_type = detail.get("credential_type")
                        if isinstance(credential_type, int):
                            credential_type = name_cache.get("api/controller/v2/credential_types/", {}).get(credential_type)
                        if credential_type:
                            object_data["credential_type"] = credential_type
                    organization = detail.get("organization")
                    if isinstance(organization, int):
                        organization_cache_endpoint = (
                            GATEWAY_ORGANIZATION_ENDPOINT if object_endpoint.startswith("api/gateway/") else CONTROLLER_ORGANIZATION_ENDPOINT
                        )
                        organization = name_cache.get(organization_cache_endpoint, {}).get(organization)
                        if organization is None:
                            if not hasattr(self, "_non_restorable_role_assignments"):
                                self._non_restorable_role_assignments = []
                            self._non_restorable_role_assignments.append(
                                dict(item, object_id=object_id, non_restorable_reason="object organization could not be resolved to a portable name")
                            )
                            continue
                    if organization:
                        object_data["organization"] = organization
                    if res_type == "role_user_assignments":
                        item.update({"object_name": object_data["name"], "object_type": object_data["type"]})
                        if object_data.get("credential_type"):
                            item["object_credential_type"] = object_data["credential_type"]
                        if organization:
                            item["organization"] = organization
                    else:
                        item["assignment_objects"] = [object_data]
                elif assignment.get("object_ansible_id"):
                    item["object_ansible_id"] = assignment["object_ansible_id"]
                else:
                    if not hasattr(self, "_non_restorable_role_assignments"):
                        self._non_restorable_role_assignments = []
                    self._non_restorable_role_assignments.append(
                        dict(item, object_id=object_id, non_restorable_reason="object reference could not be converted to a portable name")
                    )
                    continue
            elif assignment.get("object_ansible_id"):
                item["object_ansible_id"] = assignment["object_ansible_id"]
            elif object_id is not None:
                if not hasattr(self, "_non_restorable_role_assignments"):
                    self._non_restorable_role_assignments = []
                self._non_restorable_role_assignments.append(
                    dict(item, object_id=object_id, non_restorable_reason="object reference could not be converted to a portable name")
                )
                continue
            exported.append(item)
        return exported

    def _build_role_assignment_export_cache(self, manager, assignments, max_objects):
        """Bulk-load role definitions and assignment target objects before conversion."""
        role_definitions = manager.search_api(
            endpoint=ROLE_DEFINITION_ENDPOINT,
            return_all=True,
            max_objects=max_objects,
        ).get("results", [])
        role_definition_cache = {str(entry.get("id")): entry for entry in role_definitions if isinstance(entry, dict) and entry.get("id") is not None}

        endpoints = set()
        for assignment in assignments:
            summary = assignment.get("summary_fields", {})
            role = summary.get("role_definition", {})
            content = summary.get("content_object", {})
            service = content.get("service")
            model = content.get("model_name")
            role_content_type = role.get("content_type")
            role_id = role.get("id")
            if not role_content_type and role_id is not None:
                role_content_type = role_definition_cache.get(str(role_id), {}).get("content_type")
            if not (service and model) and isinstance(role_content_type, str) and "." in role_content_type:
                service, model = role_content_type.split(".", 1)
            object_type_path = ROLE_OBJECT_TYPE_MAP.get((service, model))
            if object_type_path:
                endpoints.add(object_type_path[1])

        object_cache = {}
        for object_endpoint in endpoints:
            lookup = manager.search_api(endpoint=object_endpoint, return_all=True, max_objects=max_objects)
            entries = [entry for entry in lookup.get("results", []) if isinstance(entry, dict)]
            by_id = {str(entry.get("id")): entry for entry in entries if entry.get("id") is not None}
            by_ansible_id = {}
            for entry in entries:
                ansible_id = entry.get("ansible_id") or ((entry.get("summary_fields") or {}).get("resource") or {}).get("ansible_id")
                if ansible_id:
                    by_ansible_id[str(ansible_id)] = entry
            object_cache[object_endpoint] = {"by_id": by_id, "by_ansible_id": by_ansible_id}
        return role_definition_cache, object_cache

    def _export_resource_type(self, manager, res_type, endpoint, id_field, name_cache, names_filter, max_objects):
        """Export all (or filtered) resources of one type."""
        response = self._search_resources(manager, endpoint, id_field, names_filter, max_objects)
        results = response.get("results", [])
        if not results:
            return []

        exported = []
        for resource in results:
            # Managed credential types are implementation details, but managed
            # organizations (for example Gateway's Default organization) are
            # still portable metadata and must remain in the export.
            if res_type == "credential_types" and resource.get("managed"):
                continue
            if res_type == "users" and resource.get("username") == "admin":
                # The built-in admin account owns the import connection and
                # must not have its password changed by a portable import.
                continue
            if res_type == "credentials" and resource.get("name") in MANAGED_CREDENTIAL_NAMES:
                # Managed credentials cannot be modified by the Controller API.
                continue
            if res_type == "execution_environments" and resource.get("name") in MANAGED_EXECUTION_ENVIRONMENT_NAMES:
                # Managed execution environments only permit a limited pull-field
                # update and should be supplied by the target installation.
                continue
            if res_type == "job_templates" and not resource.get("project"):
                # Controller cannot create a job template without a project;
                # omit invalid legacy/orphaned templates from portable assets.
                continue

            cleaned = self._clean_resource(resource, name_cache, res_type)
            association_reasons = self._fetch_associations(manager, res_type, resource, cleaned, name_cache, endpoint, max_objects)
            if res_type == "workflow_job_templates":
                node_data, reasons = export_workflow_nodes(manager, resource["id"], max_objects)
                reasons.extend(association_reasons)
                cleaned["workflow_nodes"] = node_data
                scope = workflow_organization_name(resource)
                if scope:
                    cleaned["organization"] = scope
                for field, collection in (("inventory", "inventories"), ("webhook_credential", "credentials")):
                    resource_id = cleaned.get(field)
                    if type(resource_id) is not int:
                        continue
                    dependency = read_named_workflow_dependency(manager, collection, resource_id)
                    # Import scopes these names to the workflow's organization and treats numeric strings as IDs.
                    if dependency is not None and (resource.get("organization") is None or dependency.get("organization") == resource["organization"]):
                        name = dependency["name"]
                        if not name.strip().isdigit():
                            cleaned[field] = name
                for field in ("organization", "inventory", "webhook_credential"):
                    if type(cleaned.get(field)) is int:
                        del cleaned[field]
                        reasons.append(f"workflow {field} could not be resolved")
                if reasons:
                    cleaned["non_restorable_reason"] = "; ".join(reasons)
                    self._display.warning("Workflow %r is not restorable: %s" % (cleaned.get("name"), cleaned["non_restorable_reason"]))
            if res_type == "credentials":
                # _clean_resource strips API response owners before association
                # fetching; repeat after fetching because owner associations are
                # added back by _fetch_associations.
                self._strip_credential_owner_fields(cleaned)
            exported.append(cleaned)

        return exported

    def _clean_resource(self, resource, name_cache, resource_type=None):
        """Strip internal fields and resolve FK IDs to names."""
        cleaned = {}
        for key, value in resource.items():
            if resource_type == "credentials" and key in {"cloud", "kind", "kubernetes"}:
                # Controller response metadata; these are not controller_credential
                # module parameters and cause import validation failures.
                continue
            if resource_type == "instance_groups" and key in {"policy_instance_list", "instances"}:
                # Instance assignments and policy lists refer to the source
                # Controller's runtime nodes and are not portable.
                continue
            if resource_type in {"job_templates", "workflow_job_templates", "inventory_sources"} and key in {"extra_vars", "source_vars"}:
                cleaned[key] = self._normalize_variables(value)
                continue
            if resource_type in {"job_templates", "workflow_job_templates"} and key == "webhook_service" and value in (None, ""):
                # Empty API values are not valid for the module's choice field.
                continue
            if resource_type == "execution_environments" and key == "pull" and value in (None, ""):
                # The module default is the valid Controller value: missing.
                continue
            if resource_type == "authenticators" and key == "slug":
                # Slugs are instance-local identifiers; authenticator maps use
                # the portable authenticator name instead.
                continue
            if resource_type == "users" and key in {"authenticator_uid", "authenticators"}:
                # The associated_authenticators mapping below is the portable
                # representation. Do not emit the deprecated ID-based fields.
                continue
            if resource_type == "users" and key == "associated_authenticators":
                authenticator_cache = name_cache.get("api/gateway/v1/authenticators/", {})
                cleaned[key] = {"name:%s" % authenticator_cache.get(int(auth_id), auth_id): data for auth_id, data in (value or {}).items()}
                continue
            if key == "organization_ids":
                organization_cache = name_cache.get(GATEWAY_ORGANIZATION_ENDPOINT, {})
                cleaned["organizations"] = [str(organization_cache.get(org_id, org_id)) for org_id in (value or [])]
                continue
            if key in STRIP_FIELDS and key not in RESOURCE_FIELDS_TO_PRESERVE.get(resource_type, frozenset()):
                continue
            if key in FK_RESOLUTION_MAP:
                resource_service = "gateway" if resource_type in GATEWAY_RESOURCE_TYPES else "controller"
                endpoint_override = GATEWAY_ORGANIZATION_ENDPOINT if key == "organization" and resource_service == "gateway" else None
                cleaned[key] = self._resolve_fk(key, value, name_cache, endpoint_override)
                if resource_type == "job_templates" and key == "inventory" and isinstance(value, int):
                    inventory_org_id = name_cache.get("api/controller/v2/inventories/:organizations", {}).get(value)
                    if inventory_org_id is not None:
                        cleaned["inventory_organization"] = self._resolve_fk("organization", inventory_org_id, name_cache, CONTROLLER_ORGANIZATION_ENDPOINT)
            elif key == "variables":
                cleaned[key] = self._normalize_variables(value)
            else:
                cleaned[key] = value
        if resource_type == "credentials":
            # First pass: remove organization-scoped RBAC owners from the raw
            # API representation. A second pass after association fetching is
            # required because _fetch_associations can re-add those fields.
            self._strip_credential_owner_fields(cleaned)
        normalizer_name = self._RESOURCE_NORMALIZERS.get(resource_type)
        if normalizer_name:
            getattr(self, normalizer_name)(cleaned)
        if resource_type == "job_templates" and cleaned.get("inventory") is None:
            # The Controller API requires either an inventory or a launch-time
            # inventory prompt. Preserve such templates in an importable form.
            cleaned["ask_inventory_on_launch"] = True
        return cleaned

    @staticmethod
    def _normalize_project(resource):
        """Normalize Controller project fields for portable imports."""
        if resource.get("scm_type") == "":
            # Controller represents manual projects with an empty string.
            resource["scm_type"] = "manual"
        # Do not launch or wait for source-control sync during import.
        resource["wait"] = False

    @staticmethod
    def _strip_credential_owner_fields(resource):
        """Remove owner fields when organization scope is present.

        Controller returns both organization scope and RBAC owner associations,
        while controller_credential accepts only one ownership mode. Owners are
        recreated later by the portable role-assignment assets.
        """
        if resource.get("organization") is not None:
            resource.pop("user", None)
            resource.pop("team", None)

    @staticmethod
    def _normalize_variables(value):
        """Convert Controller's YAML-encoded variables to module input form."""
        if not isinstance(value, str):
            return value
        if not value.strip():
            return {}
        try:
            parsed = yaml.safe_load(value)
        except yaml.YAMLError:
            return value
        if parsed is None:
            return {}
        return parsed if isinstance(parsed, dict) else value

    def _fetch_associations(self, manager, res_type, raw_resource, cleaned, name_cache, base_endpoint, max_objects):
        """Inline associations and return reasons required data could not be exported."""
        resource_id = raw_resource.get("id")
        if not resource_id:
            return []

        associations = list(RESOURCE_ASSOCIATIONS.get(res_type, []))
        if res_type == "inventory":
            associations.extend(RESOURCE_ASSOCIATIONS_INVENTORY)

        if not associations:
            return []
        reasons = []
        detail_endpoint = "%s%d/" % (base_endpoint, resource_id)

        for assoc_key, sub_suffix, mode in associations:
            sub_endpoint = "%s%s" % (detail_endpoint, sub_suffix)
            try:
                response = manager.search_api(
                    endpoint=sub_endpoint,
                    return_all=True,
                    max_objects=max_objects,
                )

                if mode == "names":
                    results = response.get("results", [])
                    names = [r.get("name", str(r.get("id", ""))) for r in results]
                    if names:
                        cleaned[assoc_key] = names

                elif mode in ("names_or_usernames", "names_or_hostnames"):
                    results = response.get("results", [])
                    preferred = "username" if mode == "names_or_usernames" else "hostname"
                    names = [r.get(preferred, r.get("name", str(r.get("id", "")))) for r in results]
                    if names:
                        if mode == "names_or_hostnames":
                            cleaned[assoc_key] = names
                        else:
                            # Credential ownership is singular in the Controller
                            # credential input contract; retain the first owner.
                            if len(names) > 1:
                                self._display.vvv(
                                    "Credential '%s' has %d owners; exporting only the first owner '%s' "
                                    "because controller_credential accepts one owner." % (cleaned.get("name", "<unnamed>"), len(names), names[0])
                                )
                            cleaned[assoc_key] = names[0]

                elif mode == "dict":
                    if response and response.get("name") is not None:
                        cleaned[assoc_key] = response
                    elif response and response.get("spec"):
                        cleaned[assoc_key] = response

                elif mode == "objects":
                    results = response.get("results", [])
                    if results:
                        if assoc_key == "hosts":
                            hosts = [{k: v for k, v in r.items() if k in HOST_EXPORT_FIELDS and v is not None} for r in results]
                            for host in hosts:
                                if "variables" in host:
                                    host["variables"] = self._normalize_variables(host["variables"])
                            cleaned[assoc_key] = hosts
                        elif assoc_key == "groups":
                            objects = []
                            for r in results:
                                group_data = {k: v for k, v in r.items() if k in GROUP_EXPORT_FIELDS and v is not None}
                                if "variables" in group_data:
                                    group_data["variables"] = self._normalize_variables(group_data["variables"])
                                self._fetch_associations(manager, "group", r, group_data, name_cache, "api/controller/v2/groups/", max_objects)
                                objects.append(group_data)
                            # The importer creates all groups before applying
                            # child associations, so export order does not need
                            # recursive depth calculation.
                            cleaned[assoc_key] = objects

            except Exception as exc:
                if res_type == "workflow_job_templates" and isinstance(exc, APIError) and exc.status_code in (403, 404):
                    if assoc_key == "survey_spec" and raw_resource.get("survey_enabled"):
                        reasons.append("workflow survey_spec could not be read for the enabled survey")
                    else:
                        self._display.warning("Omitting inaccessible %s for workflow %r" % (assoc_key, cleaned.get("name")))
                    continue
                self._display.vvvv("Failed to fetch %s for %s/%d: %s" % (assoc_key, res_type, resource_id, exc))
                raise
        return reasons
