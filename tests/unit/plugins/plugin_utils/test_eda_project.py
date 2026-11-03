# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the EDA project API transform."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.eda_project import AnsibleEdaProject  # noqa: E402
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_project import EdaProjectTransformMixin_v1  # noqa: E402


class TestEdaProjectTransform(unittest.TestCase):
    """Verify EDA project API relationships are returned as names."""

    def test_from_api_hydrates_credential_and_organization_names(self):
        manager = MagicMock()
        manager.lookup_organization_names.return_value = ["Default"]
        manager.search_api.return_value = {"results": [{"id": 42, "name": "SCM Credential"}]}

        project = EdaProjectTransformMixin_v1.from_api(
            {"name": "project", "eda_credential_id": 42, "organization_id": 7},
            {"manager": manager},
        )

        self.assertIsInstance(project, AnsibleEdaProject)
        self.assertEqual(project.credential, "SCM Credential")
        self.assertEqual(project.organization_name, "Default")
        manager.lookup_organization_names.assert_called_once_with([7])
        manager.search_api.assert_called_once_with(
            "/api/eda/v1/eda-credentials/",
            query_params={"id": 42},
            service="eda",
        )

    def test_from_api_falls_back_to_api_search_when_org_reverse_lookup_is_unavailable(self):
        manager = MagicMock()
        manager.lookup_organization_names.return_value = []
        manager.search_api.return_value = {"results": [{"id": 7, "name": "Default"}]}

        project = EdaProjectTransformMixin_v1.from_api({"name": "project", "organization_id": 7}, {"manager": manager})

        self.assertEqual(project.organization_name, "Default")
        manager.search_api.assert_called_once_with("/api/gateway/v1/organizations/", query_params={"id": 7}, service="gateway")


if __name__ == "__main__":
    unittest.main()
