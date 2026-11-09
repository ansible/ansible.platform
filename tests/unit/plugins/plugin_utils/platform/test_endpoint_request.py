"""Tests for shared endpoint request construction."""

import unittest

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import EndpointOperation, TransformContext, build_endpoint_request


class TestBuildEndpointRequest(unittest.TestCase):
    def test_projects_declared_fields_and_resolves_path_values(self):
        operation = EndpointOperation(
            path="/api/controller/v2/job_templates/{id}/launch/",
            method="POST",
            fields=["inventory", "limit", "extra_vars"],
            path_params=["id"],
        )
        context = TransformContext(manager=None, session=None, cache={}, api_version="2", service="controller", operation="launch")

        path, payload = build_endpoint_request(
            operation,
            {"inventory": 17, "limit": None, "extra_vars": {"env": "test"}, "wait": True},
            context,
            path_values={"id": 42},
        )

        self.assertEqual(
            {"path": path, "payload": payload},
            {
                "path": "/api/controller/v2/job_templates/42/launch/",
                "payload": {"inventory": 17, "extra_vars": {"env": "test"}},
            },
        )

    def test_preserves_explicit_nulls_and_flattened_body(self):
        operation = EndpointOperation(path="/api/gateway/v1/settings/", method="PATCH", fields=["settings"], flatten_body=True)
        context = TransformContext(manager=None, session=None, cache={}, api_version="1", service="gateway", operation="update")

        path, payload = build_endpoint_request(operation, {"settings": {"FOO": None}}, context)

        self.assertEqual({"path": path, "payload": payload}, {"path": "/api/gateway/v1/settings/", "payload": {"FOO": None}})

    def test_keeps_only_declared_null_fields(self):
        operation = EndpointOperation(path="/api/controller/v2/hosts/{id}/", method="PATCH", fields=["name", "organization"], path_params=["id"])
        context = TransformContext(manager=None, session=None, cache={}, api_version="2", service="controller", operation="update")

        path, payload = build_endpoint_request(operation, {"id": 5, "name": None, "organization": None}, context, fields_to_null={"name"})

        self.assertEqual({"path": path, "payload": payload}, {"path": "/api/controller/v2/hosts/5/", "payload": {"name": None}})

    def test_preserves_explicit_empty_strings_on_update(self):
        operation = EndpointOperation(
            path="/api/controller/v2/job_templates/{id}/",
            method="PATCH",
            fields=["description", "scm_branch", "limit", "name"],
            path_params=["id"],
        )
        context = TransformContext(manager=None, session=None, cache={}, api_version="1", service="eda", operation="update")

        path, payload = build_endpoint_request(
            operation,
            {"id": 3, "description": "", "scm_branch": "", "limit": "", "name": ""},
            context,
        )

        self.assertEqual(
            {"path": path, "payload": payload},
            {
                "path": "/api/controller/v2/job_templates/3/",
                "payload": {"description": "", "scm_branch": "", "limit": "", "name": ""},
            },
        )

    def test_preserves_explicit_empty_strings_on_create(self):
        operation = EndpointOperation(
            path="/api/controller/v2/job_templates/",
            method="POST",
            fields=["description", "limit"],
        )
        context = TransformContext(manager=None, session=None, cache={}, api_version="2", service="controller", operation="create")

        _, payload = build_endpoint_request(operation, {"description": "", "limit": ""}, context)

        self.assertEqual(payload, {"description": "", "limit": ""})


if __name__ == "__main__":
    unittest.main()
