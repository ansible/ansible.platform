# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the execution_environment v1 transform mixin (AAP-91391)."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.execution_environment import (  # noqa: E402
    AnsibleExecutionEnvironment,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.execution_environment import (  # noqa: E402
    ExecutionEnvironmentTransformMixin_v1,
)


def _make_context(lookup_returns=None, default=1):
    manager = MagicMock()
    if lookup_returns is not None:

        def _side_effect(endpoint, field, value):
            return lookup_returns.get((endpoint, value), default)

        manager.lookup_resource_id.side_effect = _side_effect
    else:
        manager.lookup_resource_id.return_value = default
    context = MagicMock()
    context.manager = manager
    return context


class TestExecutionEnvironmentTransform(unittest.TestCase):
    def test_from_ansible_data_resolves_organization_and_credential(self):
        ansible = AnsibleExecutionEnvironment(name="EE", image="quay.io/x", organization="Default", credential="Some Cred")
        lookups = {
            ("/api/controller/v2/organizations/", "Default"): 10,
            ("/api/controller/v2/credentials/", "Some Cred"): 20,
        }
        context = _make_context(lookup_returns=lookups)

        api = ExecutionEnvironmentTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.organization, 10)
        self.assertEqual(api.credential, 20)
        self.assertEqual(api.image, "quay.io/x")

    def test_from_ansible_data_uses_new_name_when_set(self):
        ansible = AnsibleExecutionEnvironment(name="old", image="quay.io/x", new_name="new")
        context = _make_context()

        api = ExecutionEnvironmentTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.name, "new")

    def test_from_ansible_data_includes_id_for_update_url(self):
        ansible = AnsibleExecutionEnvironment(name="EE", image="quay.io/x", id=55)
        context = _make_context()

        api = ExecutionEnvironmentTransformMixin_v1.from_ansible_data(ansible, context)

        self.assertEqual(api.id, 55)

    def test_from_api_maps_fields(self):
        ansible = ExecutionEnvironmentTransformMixin_v1.from_api(
            {"id": 1, "name": "EE", "image": "quay.io/x", "organization": 10, "credential": 20, "pull": "always"},
            _make_context(),
        )

        self.assertEqual(ansible.organization, "10")
        self.assertEqual(ansible.credential, "20")
        self.assertEqual(ansible.pull, "always")

    def test_get_endpoint_operations_use_controller_paths(self):
        ops = ExecutionEnvironmentTransformMixin_v1.get_endpoint_operations()
        for op_name in ("create", "list"):
            self.assertTrue(ops[op_name].path.startswith("/api/controller/v2/execution_environments"))

    def test_get_lookup_field_is_name(self):
        self.assertEqual(ExecutionEnvironmentTransformMixin_v1.get_lookup_field(), "name")


if __name__ == "__main__":
    unittest.main()
