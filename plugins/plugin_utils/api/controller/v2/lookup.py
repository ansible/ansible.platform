"""Shared lookup helpers for Controller API v2 transforms."""


def lookup_resource_id_with_scope(manager, endpoint, lookup_field, lookup_value, scope_field, scope_value, service, api_version):
    """Resolve a resource ID by an exact field value within a scoped resource."""
    if scope_value is None:
        raise ValueError("Cannot look up %s without a value for scope field %s" % (endpoint, scope_field))

    endpoint_path = "/api/%s/v%s/%s/" % (service, api_version, endpoint)
    response = manager.search_api(endpoint_path, query_params={lookup_field: lookup_value, scope_field: scope_value})
    results = response.get("results", [])
    matches = [result for result in results if result.get(lookup_field) == lookup_value]

    if not matches:
        raise ValueError("Resource '%s' with %s=%r and %s=%r not found" % (endpoint, lookup_field, lookup_value, scope_field, scope_value))
    if len(matches) > 1:
        raise ValueError("Multiple '%s' resources found with %s=%r and %s=%r" % (endpoint, lookup_field, lookup_value, scope_field, scope_value))

    resource_id = matches[0].get("id")
    if resource_id is None:
        raise ValueError("Resource '%s' with %s=%r and %s=%r has no ID" % (endpoint, lookup_field, lookup_value, scope_field, scope_value))
    return resource_id
