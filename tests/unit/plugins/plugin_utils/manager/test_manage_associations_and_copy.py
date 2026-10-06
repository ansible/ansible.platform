# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for PlatformService.manage_associations/manage_sub_resource/copy_resource."""

from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService

__metaclass__ = type


def _service(base_url="https://gw.example.com"):
    service = PlatformService.__new__(PlatformService)
    service.record_activity = MagicMock()
    service.session = MagicMock()
    service.cache = {}
    service.base_url = base_url
    service.request_timeout = 30
    service.config = None
    service.verify_ssl = True
    service.ca_bundle = None
    service.lookup_resource_id = MagicMock()
    service.search_api = MagicMock()
    return service


def _resp(status_code=200, json_data=None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    r.raise_for_status = MagicMock()
    return r


class TestManageAssociations(unittest.TestCase):
    def setUp(self):
        self.svc = _service()

    def test_associates_and_disassociates_to_reconcile(self):
        self.svc.search_api.return_value = {"results": [{"id": 1}, {"id": 2}]}
        self.svc.lookup_resource_id.side_effect = lambda endpoint, field, value, service: {"cred-a": 3}[value]

        changed = self.svc.manage_associations(
            "/api/controller/v2/job_templates",
            42,
            "credentials",
            ["cred-a", 1],
            "credentials",
            "name",
            service="controller",
        )

        self.assertTrue(changed)
        expected_url = "https://gw.example.com/api/controller/v2/job_templates/42/credentials/"
        self.assertTrue(all(c.args[0] == expected_url for c in self.svc.session.post.call_args_list))
        payloads = [c.kwargs["json"] for c in self.svc.session.post.call_args_list]
        self.assertIn({"id": 3, "associate": True}, payloads)
        self.assertIn({"id": 2, "disassociate": True}, payloads)

    def test_no_change_when_already_in_sync(self):
        self.svc.search_api.return_value = {"results": [{"id": 1}]}

        changed = self.svc.manage_associations(
            "/api/controller/v2/job_templates",
            42,
            "credentials",
            [1],
            "credentials",
            "name",
        )

        self.assertFalse(changed)
        self.svc.session.post.assert_not_called()

    def test_numeric_desired_items_skip_lookup(self):
        self.svc.search_api.return_value = {"results": []}

        self.svc.manage_associations("/api/controller/v2/job_templates", 42, "credentials", [5], "credentials", "name")

        self.svc.lookup_resource_id.assert_not_called()

    def test_current_associations_are_paginated(self):
        """Regression test: associations beyond page 1 must not be treated as absent."""
        # 30 existing associations (ids 1-30), spanning what would be 2 pages at page_size=25.
        self.svc.search_api.return_value = {"results": [{"id": i} for i in range(1, 31)]}

        changed = self.svc.manage_associations("/api/controller/v2/job_templates", 42, "credentials", list(range(1, 31)), "credentials", "name")

        # All 30 are already associated and desired — nothing to do, and crucially no
        # disassociate calls for ids that would have been invisible without pagination.
        self.assertFalse(changed)
        self.svc.session.post.assert_not_called()
        self.svc.search_api.assert_called_once_with("/api/controller/v2/job_templates/42/credentials/", return_all=True, max_objects=100000)


class TestManageSubResource(unittest.TestCase):
    def setUp(self):
        self.svc = _service()

    def test_none_data_is_noop(self):
        changed = self.svc.manage_sub_resource("/api/controller/v2/job_templates", 42, "survey_spec", None)
        self.assertFalse(changed)
        self.svc.session.get.assert_not_called()

    def test_empty_dict_deletes(self):
        self.svc.session.delete.return_value = _resp(status_code=200)
        changed = self.svc.manage_sub_resource("/api/controller/v2/job_templates", 42, "survey_spec", {})
        self.assertTrue(changed)
        self.svc.session.delete.assert_called_once_with("https://gw.example.com/api/controller/v2/job_templates/42/survey_spec/", timeout=30, verify=True)

    def test_empty_dict_delete_404_is_not_changed(self):
        self.svc.session.delete.return_value = _resp(status_code=404)
        changed = self.svc.manage_sub_resource("/api/controller/v2/job_templates", 42, "survey_spec", {})
        self.assertFalse(changed)

    def test_same_data_is_noop(self):
        spec = {"name": "survey", "spec": []}
        self.svc.session.get.return_value = _resp(json_data=spec)
        changed = self.svc.manage_sub_resource("/api/controller/v2/job_templates", 42, "survey_spec", spec)
        self.assertFalse(changed)
        self.svc.session.post.assert_not_called()

    def test_different_data_posts_update(self):
        self.svc.session.get.return_value = _resp(json_data={"name": "old"})
        new_spec = {"name": "new"}
        changed = self.svc.manage_sub_resource("/api/controller/v2/job_templates", 42, "survey_spec", new_spec)
        self.assertTrue(changed)
        self.svc.session.post.assert_called_once_with(
            "https://gw.example.com/api/controller/v2/job_templates/42/survey_spec/", json=new_spec, timeout=30, verify=True
        )


class TestCopyResource(unittest.TestCase):
    def setUp(self):
        self.svc = _service()

    def test_numeric_source_skips_lookup(self):
        self.svc.session.post.return_value = _resp(json_data={"id": 99, "name": "copied"})

        result = self.svc.copy_resource("job_template", "7", "copied", "/api/controller/v2/job_templates")

        self.svc.session.get.assert_not_called()
        self.svc.session.post.assert_called_once_with(
            "https://gw.example.com/api/controller/v2/job_templates/7/copy/", json={"name": "copied"}, timeout=30, verify=True
        )
        self.assertEqual(result, {"id": 99, "name": "copied"})

    def test_name_source_resolves_via_lookup_then_copies(self):
        self.svc.session.get.return_value = _resp(json_data={"results": [{"id": 12}]})
        self.svc.session.post.return_value = _resp(json_data={"id": 99})

        self.svc.copy_resource("job_template", "source jt", "copied", "/api/controller/v2/job_templates")

        self.svc.session.post.assert_called_once_with(
            "https://gw.example.com/api/controller/v2/job_templates/12/copy/", json={"name": "copied"}, timeout=30, verify=True
        )

    def test_source_not_found_raises(self):
        self.svc.session.get.return_value = _resp(json_data={"results": []})

        with self.assertRaises(ValueError):
            self.svc.copy_resource("job_template", "missing", "copied", "/api/controller/v2/job_templates")


if __name__ == "__main__":
    unittest.main()
