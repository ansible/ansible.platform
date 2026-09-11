# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for service_cluster v1 transform of outlier local-origin options.

Omitted values must not be sent (gateway defaults stay in place). False and 0
must be sent so they are not treated as unset.
"""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path

# Lives in plugin_utils/ (not plugin_utils/platform/) to avoid shadowing stdlib ``platform`` on import.
_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.service_cluster import (  # noqa: E402
    AnsibleServiceCluster,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.v1.service_cluster import (  # noqa: E402
    ServiceClusterTransformMixin_v1,
)

_SPLIT = "outlier_detection_split_external_local_origin_errors"
_CONSECUTIVE = "outlier_detection_consecutive_local_origin_failure"


class TestServiceClusterOutlierLocalOriginTransform(unittest.TestCase):
    """Ansible ↔ API mapping for AAP-76998 service_cluster options."""

    def test_create_and_update_operations_include_local_origin_fields(self):
        ops = ServiceClusterTransformMixin_v1.get_endpoint_operations()
        for op_name in ("create", "update"):
            self.assertIn(_SPLIT, ops[op_name].fields)
            self.assertIn(_CONSECUTIVE, ops[op_name].fields)

    def test_create_omits_unset_local_origin_fields(self):
        ansible = AnsibleServiceCluster(name="controller")
        api = ServiceClusterTransformMixin_v1.from_ansible_data(ansible, {"operation": "create"})
        self.assertEqual(api.name, "controller")
        self.assertIsNone(getattr(api, _SPLIT))
        self.assertIsNone(getattr(api, _CONSECUTIVE))

    def test_create_includes_explicit_split_and_consecutive_zero(self):
        ansible = AnsibleServiceCluster(
            name="controller",
            outlier_detection_split_external_local_origin_errors=True,
            outlier_detection_consecutive_local_origin_failure=0,
        )
        api = ServiceClusterTransformMixin_v1.from_ansible_data(ansible, {"operation": "create"})
        self.assertIs(getattr(api, _SPLIT), True)
        self.assertEqual(getattr(api, _CONSECUTIVE), 0)

    def test_create_includes_split_false(self):
        ansible = AnsibleServiceCluster(
            name="controller",
            outlier_detection_split_external_local_origin_errors=False,
        )
        api = ServiceClusterTransformMixin_v1.from_ansible_data(ansible, {"operation": "create"})
        self.assertIs(getattr(api, _SPLIT), False)
        self.assertIsNone(getattr(api, _CONSECUTIVE))

    def test_update_includes_non_default_consecutive_threshold(self):
        ansible = AnsibleServiceCluster(
            name="controller",
            outlier_detection_consecutive_local_origin_failure=50,
        )
        api = ServiceClusterTransformMixin_v1.from_ansible_data(ansible, {"operation": "update"})
        self.assertEqual(api.name, "controller")
        self.assertEqual(getattr(api, _CONSECUTIVE), 50)
        self.assertIsNone(getattr(api, _SPLIT))

    def test_from_api_maps_local_origin_fields(self):
        ansible = ServiceClusterTransformMixin_v1.from_api(
            {
                "name": "controller",
                "outlier_detection_split_external_local_origin_errors": True,
                "outlier_detection_consecutive_local_origin_failure": 0,
            },
            {},
        )
        self.assertEqual(ansible.name, "controller")
        self.assertIs(ansible.outlier_detection_split_external_local_origin_errors, True)
        self.assertEqual(ansible.outlier_detection_consecutive_local_origin_failure, 0)

    def test_from_api_leaves_missing_local_origin_fields_unset(self):
        ansible = ServiceClusterTransformMixin_v1.from_api({"name": "controller"}, {})
        self.assertIsNone(ansible.outlier_detection_split_external_local_origin_errors)
        self.assertIsNone(ansible.outlier_detection_consecutive_local_origin_failure)


if __name__ == "__main__":
    unittest.main()
