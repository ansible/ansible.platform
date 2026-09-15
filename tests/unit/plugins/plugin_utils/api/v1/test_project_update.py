# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the project_update v1 transform mixin (AAP-91391)."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.project_update import (  # noqa: E402
    AnsibleProjectUpdate,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.project_update import (  # noqa: E402
    ProjectUpdateTransformMixin_v1,
)


def _make_context(project_lookup_id=42):
    manager = MagicMock()
    manager.lookup_resource_id.return_value = project_lookup_id
    context = MagicMock()
    context.manager = manager
    return context


class TestProjectUpdateTransform(unittest.TestCase):
    def test_from_ansible_data_resolves_project_id_via_lookup(self):
        ansible = AnsibleProjectUpdate(name="Networking Project")
        context = _make_context(project_lookup_id=42)

        api = ProjectUpdateTransformMixin_v1.from_ansible_data(ansible, context)

        context.manager.lookup_resource_id.assert_called_once_with("/api/controller/v2/projects/", "name", "Networking Project")
        self.assertEqual(api.project_id, 42)
        self.assertIsNone(api.id)

    def test_from_ansible_data_reuses_id_when_already_set(self):
        """Second call, during a wait poll, must skip the lookup and just target {id}."""
        ansible = AnsibleProjectUpdate(name="Networking Project", id=99)
        context = _make_context()

        api = ProjectUpdateTransformMixin_v1.from_ansible_data(ansible, context)

        context.manager.lookup_resource_id.assert_not_called()
        self.assertEqual(api.id, 99)
        self.assertIsNone(api.project_id)

    def test_from_ansible_data_raises_when_project_not_found(self):
        ansible = AnsibleProjectUpdate(name="Missing Project")
        context = _make_context(project_lookup_id=None)

        with self.assertRaises(ValueError):
            ProjectUpdateTransformMixin_v1.from_ansible_data(ansible, context)

    def test_from_api_maps_launch_response(self):
        ansible = ProjectUpdateTransformMixin_v1.from_api(
            {"id": 86, "name": "Networking Project", "status": "pending", "finished": None},
            _make_context(),
        )

        self.assertEqual(ansible.id, 86)
        self.assertEqual(ansible.status, "pending")

    def test_get_endpoint_operations_target_update_and_project_updates_paths(self):
        ops = ProjectUpdateTransformMixin_v1.get_endpoint_operations()
        self.assertEqual(ops["create"].path, "/api/controller/v2/projects/{project_id}/update/")
        self.assertEqual(ops["get"].path, "/api/controller/v2/project_updates/{id}/")
        self.assertNotIn("list", ops)


if __name__ == "__main__":
    unittest.main()
