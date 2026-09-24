# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for job_template v1 transform mixin.

Covers:
- from_ansible_data: field mapping, FK resolution, extra_vars serialization
- from_api: reverse transform, FK fields returned as strings, extra_vars deserialization
- Endpoint operations: correct Controller API paths
"""

from __future__ import absolute_import, division, print_function

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.job_template import (  # noqa: E402
    AnsibleJobTemplate,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.job_template import (  # noqa: E402
    JobTemplateTransformMixin_v1,
)


class TestJobTemplateEndpointOperations(unittest.TestCase):
    """Verify endpoint paths use the Controller API v2 prefix."""

    def test_create_endpoint_path(self):
        ops = JobTemplateTransformMixin_v1.get_endpoint_operations()
        self.assertEqual(ops["create"].path, "/api/controller/v2/job_templates/")
        self.assertEqual(ops["create"].method, "POST")

    def test_update_endpoint_path(self):
        ops = JobTemplateTransformMixin_v1.get_endpoint_operations()
        self.assertEqual(ops["update"].path, "/api/controller/v2/job_templates/{id}/")
        self.assertEqual(ops["update"].method, "PATCH")

    def test_delete_endpoint_path(self):
        ops = JobTemplateTransformMixin_v1.get_endpoint_operations()
        self.assertEqual(ops["delete"].path, "/api/controller/v2/job_templates/{id}/")
        self.assertEqual(ops["delete"].method, "DELETE")

    def test_list_endpoint_path(self):
        ops = JobTemplateTransformMixin_v1.get_endpoint_operations()
        self.assertEqual(ops["list"].path, "/api/controller/v2/job_templates/")

    def test_lookup_field_is_name(self):
        self.assertEqual(JobTemplateTransformMixin_v1.get_lookup_field(), "name")


class TestJobTemplateFromAnsibleData(unittest.TestCase):
    """Test Ansible model -> API model transformation."""

    def test_basic_fields(self):
        ansible = AnsibleJobTemplate(name="Test JT", description="A test", job_type="run")
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "Test JT")
        self.assertEqual(api.description, "A test")
        self.assertEqual(api.job_type, "run")

    def test_create_uses_new_name(self):
        ansible = AnsibleJobTemplate(name="Old", new_name="New")
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "New")

    def test_update_uses_new_name(self):
        ansible = AnsibleJobTemplate(name="Old", new_name="Renamed")
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "Renamed")

    def test_update_without_new_name_keeps_name(self):
        ansible = AnsibleJobTemplate(name="Original")
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "Original")

    def test_simple_fields_pass_through(self):
        ansible = AnsibleJobTemplate(
            name="Test",
            playbook="site.yml",
            forks=10,
            verbosity=2,
            become_enabled=True,
            diff_mode=False,
            job_slice_count=3,
        )
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.playbook, "site.yml")
        self.assertEqual(api.forks, 10)
        self.assertEqual(api.verbosity, 2)
        self.assertIs(api.become_enabled, True)
        self.assertIs(api.diff_mode, False)
        self.assertEqual(api.job_slice_count, 3)

    def test_none_fields_omitted(self):
        ansible = AnsibleJobTemplate(name="Test")
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"operation": "create"})
        self.assertIsNone(api.inventory)
        self.assertIsNone(api.project)
        self.assertIsNone(api.playbook)
        self.assertIsNone(api.execution_environment)

    def test_extra_vars_dict_serialized_to_json(self):
        ansible = AnsibleJobTemplate(name="Test", extra_vars={"key": "value", "num": 42})
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"operation": "create"})
        parsed = json.loads(api.extra_vars)
        self.assertEqual(parsed, {"key": "value", "num": 42})

    def test_extra_vars_non_dict_converted_to_string(self):
        ansible = AnsibleJobTemplate(name="Test", extra_vars="key=value")
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.extra_vars, "key=value")

    def test_inventory_fk_resolved(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 42
        ansible = AnsibleJobTemplate(name="Test", inventory="My Inventory")
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"manager": manager, "operation": "create"})
        self.assertEqual(api.inventory, 42)
        manager.lookup_resource_id.assert_called_with("inventories", "name", "My Inventory")

    def test_project_fk_resolved(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 10
        ansible = AnsibleJobTemplate(name="Test", project="Demo Project")
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"manager": manager, "operation": "create"})
        self.assertEqual(api.project, 10)

    def test_execution_environment_fk_resolved(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 5
        ansible = AnsibleJobTemplate(name="Test", execution_environment="Default EE")
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"manager": manager, "operation": "create"})
        self.assertEqual(api.execution_environment, 5)

    def test_webhook_credential_fk_resolved(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 99
        ansible = AnsibleJobTemplate(name="Test", webhook_credential="GH Token")
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"manager": manager, "operation": "create"})
        self.assertEqual(api.webhook_credential, 99)

    def test_numeric_string_fk_treated_as_id(self):
        ansible = AnsibleJobTemplate(name="Test", inventory="42")
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"manager": MagicMock(), "operation": "create"})
        self.assertEqual(api.inventory, 42)

    def test_no_manager_skips_fk_resolution(self):
        ansible = AnsibleJobTemplate(name="Test", inventory="My Inventory")
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"operation": "create"})
        self.assertIsNone(api.inventory)

    def test_org_scoped_project_lookup(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 1
        manager.execute.return_value = {"id": 10, "name": "Demo"}
        ansible = AnsibleJobTemplate(name="Test", project="Demo", organization="Default")
        api = JobTemplateTransformMixin_v1.from_ansible_data(ansible, {"manager": manager, "operation": "create"})
        self.assertEqual(api.project, 10)
        manager.execute.assert_called_once()


class TestJobTemplateFromApi(unittest.TestCase):
    """Test API response -> Ansible model reverse transformation."""

    def _sample_api_data(self, **overrides):
        data = {
            "id": 1,
            "name": "Test JT",
            "description": "A test job template",
            "job_type": "run",
            "inventory": 42,
            "project": 10,
            "playbook": "site.yml",
            "execution_environment": 5,
            "webhook_credential": 99,
            "forks": 0,
            "verbosity": 0,
            "extra_vars": '{"key": "value"}',
            "created": "2026-01-01T00:00:00Z",
            "modified": "2026-01-01T00:00:00Z",
            "url": "/api/controller/v2/job_templates/1/",
        }
        data.update(overrides)
        return data

    def test_basic_fields_mapped(self):
        ansible = JobTemplateTransformMixin_v1.from_api(self._sample_api_data(), {})
        self.assertEqual(ansible.name, "Test JT")
        self.assertEqual(ansible.description, "A test job template")
        self.assertEqual(ansible.job_type, "run")
        self.assertEqual(ansible.playbook, "site.yml")
        self.assertEqual(ansible.id, 1)

    def test_fk_fields_returned_as_strings(self):
        """FK fields must be strings so _should_update can compare name vs digit-string."""
        ansible = JobTemplateTransformMixin_v1.from_api(self._sample_api_data(), {})
        self.assertEqual(ansible.inventory, "42")
        self.assertIsInstance(ansible.inventory, str)
        self.assertEqual(ansible.project, "10")
        self.assertIsInstance(ansible.project, str)
        self.assertEqual(ansible.execution_environment, "5")
        self.assertIsInstance(ansible.execution_environment, str)
        self.assertEqual(ansible.webhook_credential, "99")
        self.assertIsInstance(ansible.webhook_credential, str)

    def test_null_fk_fields_remain_none(self):
        ansible = JobTemplateTransformMixin_v1.from_api(
            self._sample_api_data(inventory=None, project=None, execution_environment=None, webhook_credential=None),
            {},
        )
        self.assertIsNone(ansible.inventory)
        self.assertIsNone(ansible.project)
        self.assertIsNone(ansible.execution_environment)
        self.assertIsNone(ansible.webhook_credential)

    def test_extra_vars_json_deserialized(self):
        ansible = JobTemplateTransformMixin_v1.from_api(
            self._sample_api_data(extra_vars='{"foo": "bar"}'),
            {},
        )
        self.assertEqual(ansible.extra_vars, {"foo": "bar"})

    def test_extra_vars_invalid_json_kept_as_string(self):
        ansible = JobTemplateTransformMixin_v1.from_api(
            self._sample_api_data(extra_vars="not-json"),
            {},
        )
        self.assertEqual(ansible.extra_vars, "not-json")

    def test_extra_vars_empty_string_passed_through(self):
        ansible = JobTemplateTransformMixin_v1.from_api(
            self._sample_api_data(extra_vars=""),
            {},
        )
        self.assertEqual(ansible.extra_vars, "")

    def test_boolean_fields_mapped(self):
        ansible = JobTemplateTransformMixin_v1.from_api(
            self._sample_api_data(
                become_enabled=True,
                diff_mode=False,
                survey_enabled=True,
                allow_simultaneous=False,
            ),
            {},
        )
        self.assertIs(ansible.become_enabled, True)
        self.assertIs(ansible.diff_mode, False)
        self.assertIs(ansible.survey_enabled, True)
        self.assertIs(ansible.allow_simultaneous, False)

    def test_read_only_fields_mapped(self):
        ansible = JobTemplateTransformMixin_v1.from_api(self._sample_api_data(), {})
        self.assertEqual(ansible.id, 1)
        self.assertEqual(ansible.created, "2026-01-01T00:00:00Z")
        self.assertEqual(ansible.url, "/api/controller/v2/job_templates/1/")


class TestJobTemplateQueryParams(unittest.TestCase):
    """Test get_find_list_query_params for org-scoped lookups."""

    def test_org_scoping(self):
        ansible = AnsibleJobTemplate(name="Test", organization="Default")
        params = JobTemplateTransformMixin_v1.get_find_list_query_params(ansible)
        self.assertEqual(params, {"organization": "Default"})

    def test_no_org_returns_empty(self):
        ansible = AnsibleJobTemplate(name="Test")
        params = JobTemplateTransformMixin_v1.get_find_list_query_params(ansible)
        self.assertEqual(params, {})


if __name__ == "__main__":
    unittest.main()
