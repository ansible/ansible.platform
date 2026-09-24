# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for PlatformService.manage_associations/manage_sub_resource/copy_resource (AAP-91390).

These are shared SDK-layer methods used by inventory (copy_from,
instance_groups/input_inventories), inventory_source and schedule
(associations) — previously only exercised indirectly via Molecule and
action-plugin flows, never with a directly mocked session.
"""

from __future__ import absolute_import, division, print_function

import unittest
from unittest.mock import MagicMock, patch

import requests
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig


def _make_platform_service(base_url="https://gw.example.com"):
    """PlatformService with network and credentials mocked."""
    mock_session = MagicMock()
    mock_requests = MagicMock()
    mock_requests.Session.return_value = mock_session
    mock_store = MagicMock()
    mock_store.get_auth_credentials.return_value = ("admin", "admin", None)
    with patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager.get_credential_manager") as mock_cred:
        mock_cred.return_value.get_or_create_store.return_value = mock_store
        with patch("ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager._get_requests") as mock_get_requests:
            mock_get_requests.return_value = mock_requests
            config = GatewayConfig(base_url=base_url, username="admin", password="admin", idle_timeout=30.0)
            return PlatformService(config)


def _resp(payload=None, status_code=200):
    r = MagicMock()
    r.status_code = status_code
    r.text = "" if payload is None else str(payload)
    r.json.return_value = payload if payload is not None else {}
    # Match real requests.Response.raise_for_status() semantics — a plain
    # MagicMock would otherwise never raise, silently defeating any test of
    # the raise_for_status() calls added to manage_associations.
    if status_code >= 400:
        r.raise_for_status.side_effect = requests.HTTPError("%s error" % status_code, response=r)
    else:
        r.raise_for_status.return_value = None
    return r


class TestManageAssociations(unittest.TestCase):
    def setUp(self):
        self.svc = _make_platform_service()

    def test_resolves_names_via_lookup_resource_id(self):
        with patch.object(self.svc, "lookup_resource_id", return_value=42) as mock_lookup:
            with patch.object(self.svc.session, "get", return_value=_resp({"results": []})):
                with patch.object(self.svc.session, "post", return_value=_resp({}, status_code=204)):
                    changed = self.svc.manage_associations(
                        "/api/controller/v2/inventories",
                        1,
                        "instance_groups",
                        ["Demo Group"],
                        "/api/controller/v2/instance_groups/",
                        "name",
                    )

        mock_lookup.assert_called_once_with("/api/controller/v2/instance_groups/", "name", "Demo Group")
        self.assertTrue(changed)

    def test_digit_string_items_skip_lookup(self):
        with patch.object(self.svc, "lookup_resource_id") as mock_lookup:
            with patch.object(self.svc.session, "get", return_value=_resp({"results": [{"id": 5}]})):
                changed = self.svc.manage_associations(
                    "/api/controller/v2/inventories",
                    1,
                    "instance_groups",
                    ["5"],
                    "/api/controller/v2/instance_groups/",
                    "name",
                )

        mock_lookup.assert_not_called()
        self.assertFalse(changed)  # already associated, no change

    def test_associates_missing_and_disassociates_removed(self):
        with patch.object(self.svc, "lookup_resource_id", return_value=None):
            with patch.object(self.svc.session, "get", return_value=_resp({"results": [{"id": 5}]})):
                with patch.object(self.svc.session, "post", return_value=_resp({}, status_code=204)) as mock_post:
                    changed = self.svc.manage_associations(
                        "/api/controller/v2/inventories",
                        1,
                        "instance_groups",
                        ["10"],  # digit: keep 10, drop existing 5
                        "/api/controller/v2/instance_groups/",
                        "name",
                    )

        self.assertTrue(changed)
        calls = [c.kwargs["json"] for c in mock_post.call_args_list]
        self.assertIn({"id": 10, "associate": True}, calls)
        self.assertIn({"id": 5, "disassociate": True}, calls)

    def test_no_change_when_desired_matches_current(self):
        with patch.object(self.svc.session, "get", return_value=_resp({"results": [{"id": 5}]})):
            with patch.object(self.svc.session, "post") as mock_post:
                changed = self.svc.manage_associations(
                    "/api/controller/v2/inventories",
                    1,
                    "instance_groups",
                    ["5"],
                    "/api/controller/v2/instance_groups/",
                    "name",
                )

        mock_post.assert_not_called()
        self.assertFalse(changed)

    def test_raises_when_name_lookup_fails(self):
        with patch.object(self.svc, "lookup_resource_id", return_value=None):
            with self.assertRaises(ValueError):
                self.svc.manage_associations(
                    "/api/controller/v2/inventories",
                    1,
                    "instance_groups",
                    ["Missing Group"],
                    "/api/controller/v2/instance_groups/",
                    "name",
                )

    def test_get_failure_propagates_instead_of_silently_treated_as_empty(self):
        """A read failure must not be swallowed into 'no current associations' —
        that would make disassociation of anything currently associated a silent no-op."""
        with patch.object(self.svc.session, "get", return_value=_resp(status_code=500)):
            with self.assertRaises(requests.HTTPError):
                self.svc.manage_associations(
                    "/api/controller/v2/inventories",
                    1,
                    "instance_groups",
                    ["5"],
                    "/api/controller/v2/instance_groups/",
                    "name",
                )

    def test_failed_associate_post_raises_instead_of_reporting_changed(self):
        """requests.Session.post() does not raise on 4xx/5xx by itself — without
        raise_for_status() a rejected associate would be reported as a success."""
        with patch.object(self.svc, "lookup_resource_id", return_value=42):
            with patch.object(self.svc.session, "get", return_value=_resp({"results": []})):
                with patch.object(self.svc.session, "post", return_value=_resp(status_code=400)):
                    with self.assertRaises(ValueError):
                        self.svc.manage_associations(
                            "/api/controller/v2/inventories",
                            1,
                            "instance_groups",
                            ["Demo Group"],
                            "/api/controller/v2/instance_groups/",
                            "name",
                        )


class TestManageSubResource(unittest.TestCase):
    def setUp(self):
        self.svc = _make_platform_service()

    def test_data_none_is_a_noop(self):
        with patch.object(self.svc.session, "get") as mock_get, patch.object(self.svc.session, "post") as mock_post:
            changed = self.svc.manage_sub_resource("/api/controller/v2/job_templates", 1, "survey_spec", data=None)

        mock_get.assert_not_called()
        mock_post.assert_not_called()
        self.assertFalse(changed)

    def test_empty_dict_deletes(self):
        with patch.object(self.svc.session, "delete", return_value=_resp(status_code=204)) as mock_delete:
            changed = self.svc.manage_sub_resource("/api/controller/v2/job_templates", 1, "survey_spec", data={})

        mock_delete.assert_called_once()
        self.assertTrue(changed)

    def test_posts_when_data_differs_from_current(self):
        with patch.object(self.svc.session, "get", return_value=_resp({"name": "old"})):
            with patch.object(self.svc.session, "post", return_value=_resp({}, status_code=200)) as mock_post:
                changed = self.svc.manage_sub_resource("/api/controller/v2/job_templates", 1, "survey_spec", data={"name": "new"})

        mock_post.assert_called_once()
        self.assertTrue(changed)

    def test_no_post_when_data_matches_current(self):
        with patch.object(self.svc.session, "get", return_value=_resp({"name": "same"})):
            with patch.object(self.svc.session, "post") as mock_post:
                changed = self.svc.manage_sub_resource("/api/controller/v2/job_templates", 1, "survey_spec", data={"name": "same"})

        mock_post.assert_not_called()
        self.assertFalse(changed)

    def test_raises_on_post_failure(self):
        with patch.object(self.svc.session, "get", return_value=_resp({"name": "old"})):
            with patch.object(self.svc.session, "post", return_value=_resp({"detail": "bad request"}, status_code=400)):
                with self.assertRaises(ValueError):
                    self.svc.manage_sub_resource("/api/controller/v2/job_templates", 1, "survey_spec", data={"name": "new"})


class TestCopyResource(unittest.TestCase):
    def setUp(self):
        self.svc = _make_platform_service()

    def test_finds_by_name_and_posts_to_copy_endpoint(self):
        with patch.object(self.svc, "execute", return_value={"id": 100}) as mock_execute:
            with patch.object(self.svc.session, "post", return_value=_resp({"id": 200, "name": "Copy"}, status_code=201)) as mock_post:
                result = self.svc.copy_resource("inventory", "Source Inventory", "Copy", "/api/controller/v2/inventories")

        mock_execute.assert_called_once_with(operation="find", module_name="inventory", ansible_data_dict={"name": "Source Inventory"})
        called_url = mock_post.call_args[0][0]
        self.assertIn("/api/controller/v2/inventories/100/copy/", called_url)
        self.assertEqual(mock_post.call_args.kwargs["json"], {"name": "Copy"})
        self.assertEqual(result, {"id": 200, "name": "Copy"})

    def test_falls_back_to_id_based_lookup_when_name_lookup_fails(self):
        with patch.object(self.svc, "execute", side_effect=[ValueError("not found"), {"id": 100}]) as mock_execute:
            with patch.object(self.svc.session, "post", return_value=_resp({"id": 200}, status_code=201)):
                result = self.svc.copy_resource("inventory", "100", "Copy", "/api/controller/v2/inventories")

        self.assertEqual(mock_execute.call_count, 2)
        second_call_kwargs = mock_execute.call_args_list[1].kwargs
        self.assertEqual(second_call_kwargs["ansible_data_dict"], {"id": 100, "name": "100"})
        self.assertEqual(result, {"id": 200})

    def test_raises_when_source_not_found(self):
        with patch.object(self.svc, "execute", side_effect=ValueError("not found")):
            with self.assertRaises(ValueError):
                self.svc.copy_resource("inventory", "Missing", "Copy", "/api/controller/v2/inventories")


if __name__ == "__main__":
    unittest.main()
