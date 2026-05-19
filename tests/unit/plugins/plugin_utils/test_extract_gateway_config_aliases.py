# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for alias resolution in extract_gateway_config.

Covers the aap_* primary names and all documented aliases for every connection
parameter.  Previously only gateway_* names were resolved from task_args;
aap_validate_certs / validate_certs / aap_hostname / etc. were silently ignored
when passed as task parameters.
"""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import (  # noqa: E402
    extract_gateway_config,
)

# Minimal task args used as a base in every test
_BASE = {
    "gateway_hostname": "https://gw.example",
    "gateway_username": "admin",
    "gateway_password": "secret",
}


class TestValidateCertsAliases(unittest.TestCase):
    """validate_certs / gateway_validate_certs / aap_validate_certs aliases.

    The value False MUST be honoured.  'or'-chaining silently drops False,
    so this must use 'in' checks — the core of the bug being fixed.
    """

    def test_validate_certs_false_is_honoured(self):
        """Bug reproduction: validate_certs: false was silently ignored before the fix."""
        cfg = extract_gateway_config(
            task_args={**_BASE, "validate_certs": False},
            host_vars={},
        )
        self.assertFalse(cfg.verify_ssl, "validate_certs: false must disable SSL verification")

    def test_gateway_validate_certs_false_is_honoured(self):
        cfg = extract_gateway_config(
            task_args={**_BASE, "gateway_validate_certs": False},
            host_vars={},
        )
        self.assertFalse(cfg.verify_ssl)

    def test_aap_validate_certs_false_is_honoured(self):
        cfg = extract_gateway_config(
            task_args={**_BASE, "aap_validate_certs": False},
            host_vars={},
        )
        self.assertFalse(cfg.verify_ssl)

    def test_validate_certs_true_is_honoured(self):
        cfg = extract_gateway_config(
            task_args={**_BASE, "validate_certs": True},
            host_vars={},
        )
        self.assertTrue(cfg.verify_ssl)

    def test_default_is_true_when_not_set(self):
        cfg = extract_gateway_config(task_args=dict(_BASE), host_vars={})
        self.assertTrue(cfg.verify_ssl)

    def test_task_args_override_host_vars(self):
        """task_args must win over host_vars regardless of which alias is used."""
        cfg = extract_gateway_config(
            task_args={**_BASE, "validate_certs": False},
            host_vars={"gateway_validate_certs": True},
        )
        self.assertFalse(cfg.verify_ssl)

    def test_host_vars_alias_used_when_not_in_task_args(self):
        cfg = extract_gateway_config(
            task_args=dict(_BASE),
            host_vars={"validate_certs": False},
        )
        self.assertFalse(cfg.verify_ssl)

    def test_aap_validate_certs_takes_priority_over_gateway_validate_certs(self):
        """aap_validate_certs is the primary name; it wins over gateway_validate_certs."""
        cfg = extract_gateway_config(
            task_args={**_BASE, "aap_validate_certs": False, "gateway_validate_certs": True},
            host_vars={},
        )
        self.assertFalse(cfg.verify_ssl)


class TestHostnameAliases(unittest.TestCase):
    """aap_hostname / gateway_hostname / gateway_url aliases."""

    def test_aap_hostname_used_as_task_arg(self):
        cfg = extract_gateway_config(
            task_args={"aap_hostname": "https://aap.example", "gateway_username": "a", "gateway_password": "b"},
            host_vars={},
        )
        self.assertEqual(cfg.base_url, "https://aap.example")

    def test_gateway_hostname_still_works(self):
        cfg = extract_gateway_config(task_args=dict(_BASE), host_vars={})
        self.assertEqual(cfg.base_url, "https://gw.example")

    def test_aap_hostname_takes_priority_over_gateway_hostname(self):
        cfg = extract_gateway_config(
            task_args={**_BASE, "aap_hostname": "https://aap.example"},
            host_vars={},
        )
        self.assertEqual(cfg.base_url, "https://aap.example")


class TestCredentialAliases(unittest.TestCase):
    """aap_username / aap_password / aap_token aliases in task_args."""

    def test_aap_username_used_as_task_arg(self):
        cfg = extract_gateway_config(
            task_args={"gateway_hostname": "https://gw.example", "aap_username": "newuser", "gateway_password": "s"},
            host_vars={},
        )
        self.assertEqual(cfg.username, "newuser")

    def test_aap_password_used_as_task_arg(self):
        cfg = extract_gateway_config(
            task_args={"gateway_hostname": "https://gw.example", "gateway_username": "admin", "aap_password": "newpass"},
            host_vars={},
        )
        self.assertEqual(cfg.password, "newpass")

    def test_aap_token_used_as_task_arg(self):
        cfg = extract_gateway_config(
            task_args={"gateway_hostname": "https://gw.example", "aap_token": "mytoken123"},
            host_vars={},
        )
        self.assertEqual(cfg.oauth_token, "mytoken123")

    def test_gateway_token_still_works(self):
        cfg = extract_gateway_config(
            task_args={"gateway_hostname": "https://gw.example", "gateway_token": "legacytoken"},
            host_vars={},
        )
        self.assertEqual(cfg.oauth_token, "legacytoken")


class TestRequestTimeoutAliases(unittest.TestCase):
    """aap_request_timeout / gateway_request_timeout / request_timeout aliases."""

    def test_aap_request_timeout_used_as_task_arg(self):
        cfg = extract_gateway_config(
            task_args={**_BASE, "aap_request_timeout": 30.0},
            host_vars={},
        )
        self.assertEqual(cfg.request_timeout, 30.0)

    def test_request_timeout_alias(self):
        cfg = extract_gateway_config(
            task_args={**_BASE, "request_timeout": 45.0},
            host_vars={},
        )
        self.assertEqual(cfg.request_timeout, 45.0)

    def test_gateway_request_timeout_still_works(self):
        cfg = extract_gateway_config(
            task_args={**_BASE, "gateway_request_timeout": 20.0},
            host_vars={},
        )
        self.assertEqual(cfg.request_timeout, 20.0)

    def test_default_timeout_is_10(self):
        cfg = extract_gateway_config(task_args=dict(_BASE), host_vars={})
        self.assertEqual(cfg.request_timeout, 10.0)


if __name__ == "__main__":
    unittest.main()
