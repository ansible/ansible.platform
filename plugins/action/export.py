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

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin

# Resource types and their Controller API endpoints (in export order).
EXPORTABLE_RESOURCES = [
    ("organizations", "api/controller/v2/organizations/", "name"),
    ("users", "api/controller/v2/users/", "username"),
    ("teams", "api/controller/v2/teams/", "name"),
    ("credential_types", "api/controller/v2/credential_types/", "name"),
    ("credentials", "api/controller/v2/credentials/", "name"),
    ("execution_environments", "api/controller/v2/execution_environments/", "name"),
    ("notification_templates", "api/controller/v2/notification_templates/", "name"),
    ("projects", "api/controller/v2/projects/", "name"),
    ("inventory", "api/controller/v2/inventories/", "name"),
    ("inventory_sources", "api/controller/v2/inventory_sources/", "name"),
    ("job_templates", "api/controller/v2/job_templates/", "name"),
    ("workflow_job_templates", "api/controller/v2/workflow_job_templates/", "name"),
    ("schedules", "api/controller/v2/schedules/", "name"),
]

# FK fields and the endpoint to resolve them against.
# (field_name, api_endpoint, identifier_field)
FK_RESOLUTION_MAP = {
    "organization": ("api/controller/v2/organizations/", "name"),
    "inventory": ("api/controller/v2/inventories/", "name"),
    "project": ("api/controller/v2/projects/", "name"),
    "credential_type": ("api/controller/v2/credential_types/", "name"),
    "execution_environment": ("api/controller/v2/execution_environments/", "name"),
    "source_project": ("api/controller/v2/projects/", "name"),
    "default_environment": ("api/controller/v2/execution_environments/", "name"),
    "credential": ("api/controller/v2/credentials/", "name"),
    "webhook_credential": ("api/controller/v2/credentials/", "name"),
    "insights_credential": ("api/controller/v2/credentials/", "name"),
    "vault_credential": ("api/controller/v2/credentials/", "name"),
    "unified_job_template": ("api/controller/v2/unified_job_templates/", "name"),
}

# Fields to strip from exported resources (read-only / internal).
STRIP_FIELDS = frozenset({
    "id", "type", "url", "related", "summary_fields",
    "created", "modified", "created_by", "modified_by",
    "last_job_run", "last_job_failed", "next_job_run",
    "status", "last_update_failed", "last_updated",
    "user_capabilities", "object_roles",
})

# Association sub-endpoints to fetch per resource type.
# (export_key, sub_endpoint_suffix, mode)
# mode: "names" = extract name list, "dict" = include raw dict
RESOURCE_ASSOCIATIONS = {
    "job_templates": [
        ("credentials", "credentials/", "names"),
        ("labels", "labels/", "names"),
        ("instance_groups", "instance_groups/", "names"),
        ("survey_spec", "survey_spec/", "dict"),
    ],
    "workflow_job_templates": [
        ("labels", "labels/", "names"),
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
    "inventory": [
        ("hosts", "hosts/", "objects"),
        ("groups", "groups/", "objects"),
    ],
}

# Fields to keep when exporting hosts/groups as inline objects.
HOST_EXPORT_FIELDS = {"name", "description", "enabled", "instance_id", "variables"}
GROUP_EXPORT_FIELDS = {"name", "description", "variables"}


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "export"

    def run(self, tmp=None, task_vars=None):
        """Export resources from the platform."""
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            export_all = validated_params.get("all", False)
            all_requested = export_all or all(
                validated_params.get(res_type) is None
                for res_type, _, _ in EXPORTABLE_RESOURCES
            )

            # Build FK name cache
            self._display.vvv("Building FK name resolution cache...")
            name_cache = self._build_name_cache(manager)

            assets = {}
            for res_type, endpoint, id_field in EXPORTABLE_RESOURCES:
                filter_values = validated_params.get(res_type)

                if not all_requested and filter_values is None:
                    continue

                should_export_all = all_requested or filter_values == ["all"]
                names_filter = None if should_export_all else filter_values

                self._display.vvv("Exporting %s..." % res_type)
                exported = self._export_resource_type(
                    manager, res_type, endpoint, id_field, name_cache, names_filter
                )
                if exported:
                    assets[res_type] = exported

            result["changed"] = False
            result["failed"] = False
            result["assets"] = assets

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result

    def _build_name_cache(self, manager):
        """Pre-fetch all resource types and build {endpoint: {id: name}} cache."""
        cache = {}
        # Deduplicate endpoints from FK_RESOLUTION_MAP
        endpoints = set()
        for endpoint, id_field in FK_RESOLUTION_MAP.values():
            endpoints.add((endpoint, id_field))

        for endpoint, id_field in endpoints:
            try:
                response = manager.search_api(
                    endpoint=endpoint,
                    return_all=True,
                    max_objects=10000,
                )
                results = response.get("results", [])
                cache[endpoint] = {
                    r["id"]: r.get(id_field, r.get("name", r.get("username", str(r["id"]))))
                    for r in results
                    if "id" in r
                }
                self._display.vvvv("Cached %d entries for %s" % (len(cache[endpoint]), endpoint))
            except Exception as exc:
                self._display.warning("Failed to cache %s: %s" % (endpoint, exc))
                cache[endpoint] = {}

        return cache

    def _resolve_fk(self, field_name, value, name_cache):
        """Resolve an FK integer ID to a resource name using the cache."""
        if value is None or not isinstance(value, int):
            return value

        fk_info = FK_RESOLUTION_MAP.get(field_name)
        if not fk_info:
            return value

        endpoint, _ = fk_info
        endpoint_cache = name_cache.get(endpoint, {})
        resolved = endpoint_cache.get(value)
        if resolved is not None:
            return resolved

        self._display.vvvv("FK cache miss: %s=%d" % (field_name, value))
        return value

    def _export_resource_type(self, manager, res_type, endpoint, id_field, name_cache, names_filter):
        """Export all (or filtered) resources of one type."""
        try:
            query_params = {}
            if names_filter:
                if len(names_filter) == 1:
                    query_params[id_field] = names_filter[0]
                else:
                    query_params["or__%s" % id_field] = ",".join(names_filter)

            response = manager.search_api(
                endpoint=endpoint,
                query_params=query_params or None,
                return_all=True,
                max_objects=10000,
            )
        except Exception as exc:
            self._display.warning("Failed to fetch %s: %s" % (res_type, exc))
            return []

        results = response.get("results", [])
        if not results:
            return []

        exported = []
        for resource in results:
            if resource.get("managed"):
                continue

            cleaned = self._clean_resource(resource, name_cache)
            self._fetch_associations(manager, res_type, resource, cleaned, name_cache, endpoint)
            exported.append(cleaned)

        return exported

    def _clean_resource(self, resource, name_cache):
        """Strip internal fields and resolve FK IDs to names."""
        cleaned = {}
        for key, value in resource.items():
            if key in STRIP_FIELDS:
                continue
            if key in FK_RESOLUTION_MAP:
                cleaned[key] = self._resolve_fk(key, value, name_cache)
            else:
                cleaned[key] = value
        return cleaned

    def _fetch_associations(self, manager, res_type, raw_resource, cleaned, name_cache, base_endpoint):
        """Fetch and inline association sub-endpoints for a resource."""
        associations = RESOURCE_ASSOCIATIONS.get(res_type)
        if not associations:
            return

        resource_id = raw_resource.get("id")
        if not resource_id:
            return

        detail_endpoint = "%s%d/" % (base_endpoint, resource_id)

        for assoc_key, sub_suffix, mode in associations:
            sub_endpoint = "%s%s" % (detail_endpoint, sub_suffix)
            try:
                response = manager.search_api(
                    endpoint=sub_endpoint,
                    return_all=True,
                    max_objects=10000,
                )

                if mode == "names":
                    results = response.get("results", [])
                    names = [r.get("name", str(r.get("id", ""))) for r in results]
                    if names:
                        cleaned[assoc_key] = names

                elif mode == "dict":
                    if response and response.get("name") is not None:
                        cleaned[assoc_key] = response
                    elif response and response.get("spec"):
                        cleaned[assoc_key] = response

                elif mode == "objects":
                    results = response.get("results", [])
                    if results:
                        if assoc_key == "hosts":
                            cleaned[assoc_key] = [
                                {k: v for k, v in r.items() if k in HOST_EXPORT_FIELDS and v is not None}
                                for r in results
                            ]
                        elif assoc_key == "groups":
                            objects = []
                            for r in results:
                                group_data = {k: v for k, v in r.items() if k in GROUP_EXPORT_FIELDS and v is not None}
                                host_endpoint = "%s%d/hosts/" % (
                                    "api/controller/v2/groups/", r["id"]
                                )
                                try:
                                    host_resp = manager.search_api(endpoint=host_endpoint, return_all=True)
                                    host_names = [h.get("name") for h in host_resp.get("results", [])]
                                    if host_names:
                                        group_data["hosts"] = host_names
                                except Exception:
                                    pass
                                objects.append(group_data)
                            cleaned[assoc_key] = objects

            except Exception as exc:
                self._display.vvvv("Failed to fetch %s for %s/%d: %s" % (assoc_key, res_type, resource_id, exc))
