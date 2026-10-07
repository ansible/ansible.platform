# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the JobTemplate transform mixin (core CRUD, no associations yet)."""

from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.job_template import AnsibleJobTemplate
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.job_template import JobTemplateTransformMixin_v2
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext

__metaclass__ = type


def _context(operation, manager=None):
    return TransformContext(
        manager=manager or MagicMock(),
        session=MagicMock(),
        cache={},
        api_version="2",
        service="controller",
        operation=operation,
    )


class TestFromAnsibleDataCreate(unittest.TestCase):
    def test_create_uses_name_and_scalar_fields(self):
        manager = MagicMock()
        instance = AnsibleJobTemplate(name="Ping", job_type="run", playbook="ping.yml", forks=5)

        api_data = JobTemplateTransformMixin_v2.from_ansible_data(instance, _context("create", manager))

        self.assertEqual(api_data.name, "Ping")
        self.assertEqual(api_data.job_type, "run")
        self.assertEqual(api_data.playbook, "ping.yml")
        self.assertEqual(api_data.forks, 5)

    def test_extra_vars_dict_is_json_encoded(self):
        manager = MagicMock()
        instance = AnsibleJobTemplate(name="Ping", extra_vars={"foo": "bar"})

        api_data = JobTemplateTransformMixin_v2.from_ansible_data(instance, _context("create", manager))

        self.assertEqual(api_data.extra_vars, '{"foo": "bar"}')

    def test_inventory_execution_environment_webhook_credential_resolved_via_controller_service(self):
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = lambda endpoint, field, value, service=None: {
            ("inventories", "Local"): 10,
            ("execution_environments", "EE"): 20,
            ("credentials", "Webhook Cred"): 30,
        }[(endpoint, value)]

        instance = AnsibleJobTemplate(name="Ping", inventory="Local", execution_environment="EE", webhook_credential="Webhook Cred")

        api_data = JobTemplateTransformMixin_v2.from_ansible_data(instance, _context("create", manager))

        self.assertEqual(api_data.inventory, 10)
        self.assertEqual(api_data.execution_environment, 20)
        self.assertEqual(api_data.webhook_credential, 30)
        for call in manager.lookup_resource_id.call_args_list:
            self.assertEqual(call.kwargs.get("service"), "controller")


class TestFromAnsibleDataUpdate(unittest.TestCase):
    def test_omitted_foreign_keys_keep_api_wire_types_on_update(self):
        manager = MagicMock()
        manager.search_api.return_value = {"inventory": 10, "project": 20, "extra_vars": '{"answer": 42}'}
        instance = AnsibleJobTemplate(name="Ping", id=5, survey_enabled=True)

        api_data = JobTemplateTransformMixin_v2.from_ansible_data(instance, _context("update", manager))

        self.assertEqual(api_data.inventory, 10)
        self.assertEqual(api_data.project, 20)
        self.assertEqual(api_data.extra_vars, '{"answer": 42}')
        manager.search_api.assert_called_once_with("/api/controller/v2/job_templates/5/")

    def test_new_name_is_sent_as_name(self):
        manager = MagicMock()
        instance = AnsibleJobTemplate(name="Ping", new_name="Ping Renamed", id=5)

        api_data = JobTemplateTransformMixin_v2.from_ansible_data(instance, _context("update", manager))

        self.assertEqual(api_data.name, "Ping Renamed")
        self.assertEqual(api_data.id, 5)

    def test_plain_name_is_echoed_back(self):
        manager = MagicMock()
        instance = AnsibleJobTemplate(name="Ping", id=5)

        api_data = JobTemplateTransformMixin_v2.from_ansible_data(instance, _context("update", manager))

        self.assertEqual(api_data.name, "Ping")

    def test_numeric_name_used_for_lookup_only_not_echoed(self):
        manager = MagicMock()
        instance = AnsibleJobTemplate(name="1001", id=1001)

        api_data = JobTemplateTransformMixin_v2.from_ansible_data(instance, _context("update", manager))

        self.assertIsNone(api_data.name)


class TestProjectResolution(unittest.TestCase):
    def test_numeric_project_passthrough(self):
        manager = MagicMock()
        instance = AnsibleJobTemplate(name="Ping", project="7")

        api_data = JobTemplateTransformMixin_v2.from_ansible_data(instance, _context("create", manager))

        self.assertEqual(api_data.project, 7)
        manager.lookup_resource_id.assert_not_called()
        manager.search_api.assert_not_called()

    def test_project_without_organization_uses_plain_lookup(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 42
        instance = AnsibleJobTemplate(name="Ping", project="Demo")

        api_data = JobTemplateTransformMixin_v2.from_ansible_data(instance, _context("create", manager))

        self.assertEqual(api_data.project, 42)
        manager.lookup_resource_id.assert_called_once_with("projects", "name", "Demo", service="controller")

    def test_project_with_organization_resolves_org_then_scoped_search(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 99  # organization id
        manager.search_api.return_value = {"results": [{"id": 55, "name": "Demo"}]}
        instance = AnsibleJobTemplate(name="Ping", project="Demo", organization="Default")

        api_data = JobTemplateTransformMixin_v2.from_ansible_data(instance, _context("create", manager))

        manager.lookup_resource_id.assert_called_once_with("organizations", "name", "Default")
        manager.search_api.assert_called_once_with("/api/controller/v2/projects/", query_params={"name": "Demo", "organization": 99})
        self.assertEqual(api_data.project, 55)

    def test_project_with_organization_not_found_raises(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 99
        manager.search_api.return_value = {"results": []}
        instance = AnsibleJobTemplate(name="Ping", project="Missing", organization="Default")

        with self.assertRaises(ValueError):
            JobTemplateTransformMixin_v2.from_ansible_data(instance, _context("create", manager))


class TestFromApi(unittest.TestCase):
    def test_round_trips_scalar_fields_and_resolves_fk_ids_to_names(self):
        manager = MagicMock()
        manager.search_api.side_effect = lambda path: {
            "/api/controller/v2/inventories/10/": {"name": "Local"},
            "/api/controller/v2/projects/20/": {"name": "Demo"},
            "/api/controller/v2/execution_environments/30/": {"name": "EE"},
            "/api/controller/v2/credentials/40/": {"name": "Webhook Cred"},
        }[path]
        api_data = {
            "id": 5,
            "name": "Ping",
            "job_type": "run",
            "inventory": 10,
            "project": 20,
            "execution_environment": 30,
            "webhook_credential": 40,
            "extra_vars": '{"foo": "bar"}',
            "created": "2026-01-01T00:00:00Z",
            "modified": "2026-01-02T00:00:00Z",
            "url": "/api/controller/v2/job_templates/5/",
        }

        result = JobTemplateTransformMixin_v2.from_api(api_data, _context("find", manager=manager))

        self.assertEqual(result.id, 5)
        self.assertEqual(result.name, "Ping")
        # FK fields must come back as names (str), matching the Optional[str] dataclass
        # fields and the user-supplied input — returning raw ids here would make
        # _should_update() compare a name against an int and always report "changed".
        self.assertEqual(result.inventory, "Local")
        self.assertEqual(result.project, "Demo")
        self.assertEqual(result.execution_environment, "EE")
        self.assertEqual(result.webhook_credential, "Webhook Cred")
        self.assertEqual(result.extra_vars, {"foo": "bar"})
        self.assertEqual(result.created, "2026-01-01T00:00:00Z")
        self.assertEqual(result.url, "/api/controller/v2/job_templates/5/")

    def test_fk_name_resolution_is_cached(self):
        manager = MagicMock()
        manager.search_api.return_value = {"name": "Local"}
        context = _context("find", manager=manager)

        JobTemplateTransformMixin_v2.from_api({"name": "Ping", "inventory": 10}, context)
        JobTemplateTransformMixin_v2.from_api({"name": "Ping2", "inventory": 10}, context)

        manager.search_api.assert_called_once_with("/api/controller/v2/inventories/10/")

    def test_fk_lookup_failure_falls_back_to_none_rather_than_raising(self):
        manager = MagicMock()
        manager.search_api.side_effect = ValueError("not found")

        result = JobTemplateTransformMixin_v2.from_api({"name": "Ping", "inventory": 10}, _context("find", manager=manager))

        self.assertIsNone(result.inventory)

    def test_null_fk_id_skips_lookup(self):
        manager = MagicMock()

        result = JobTemplateTransformMixin_v2.from_api({"name": "Ping"}, _context("find", manager=manager))

        self.assertIsNone(result.inventory)
        manager.search_api.assert_not_called()

    def test_non_json_extra_vars_falls_back_to_none(self):
        result = JobTemplateTransformMixin_v2.from_api({"name": "Ping", "extra_vars": "not json"}, _context("find"))
        self.assertIsNone(result.extra_vars)


class TestEndpointOperations(unittest.TestCase):
    def test_paths_include_controller_service_segment(self):
        operations = JobTemplateTransformMixin_v2.get_endpoint_operations()
        self.assertEqual(operations["create"].path, "/api/controller/v2/job_templates/")
        self.assertEqual(operations["update"].path, "/api/controller/v2/job_templates/{id}/")
        self.assertEqual(operations["delete"].path, "/api/controller/v2/job_templates/{id}/")
        self.assertEqual(operations["list"].path, "/api/controller/v2/job_templates/")

    def test_lookup_field_is_name(self):
        self.assertEqual(JobTemplateTransformMixin_v2.get_lookup_field(), "name")


if __name__ == "__main__":
    unittest.main()
