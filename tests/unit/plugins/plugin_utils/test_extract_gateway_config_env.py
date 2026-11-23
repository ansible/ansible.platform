# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for environment variable resolution in extract_gateway_config.

The action plugin path (plugins/action/base_action.py) resolves gateway
credentials on the control node before the module runs, so it never reached the
``env_fallback`` entries in plugins/module_utils/aap_module.py.  Exporting
GATEWAY_HOSTNAME and running a playbook therefore failed with
"gateway_url or gateway_hostname must be provided", despite the documentation
in plugins/doc_fragments/auth.py promising the fallback.

Every test passes an explicit ``env`` mapping so results do not depend on the
environment of the machine running the suite.
"""

from __future__ import absolute_import, division, print_function

import os
import sys
import unittest
from pathlib import Path

_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import (  # noqa: E402
    extract_gateway_config,
)


class TestHostnameFromEnv(unittest.TestCase):
    """GATEWAY_HOSTNAME / AAP_HOSTNAME resolution."""

    def test_gateway_hostname_env_is_used(self):
        """Bug reproduction: exported GATEWAY_HOSTNAME was ignored before the fix."""
        cfg = extract_gateway_config(
            task_args={},
            host_vars={},
            env={"GATEWAY_HOSTNAME": "https://gw.example"},
        )
        self.assertEqual(cfg.base_url, "https://gw.example")

    def test_aap_hostname_env_is_used(self):
        cfg = extract_gateway_config(task_args={}, host_vars={}, env={"AAP_HOSTNAME": "https://gw.example"})
        self.assertEqual(cfg.base_url, "https://gw.example")

    def test_gateway_hostname_wins_over_aap_hostname(self):
        """Matches env_fallback (first match wins) and the lookup env: ordering (last match wins)."""
        cfg = extract_gateway_config(
            task_args={},
            host_vars={},
            env={"GATEWAY_HOSTNAME": "https://gateway.example", "AAP_HOSTNAME": "https://aap.example"},
        )
        self.assertEqual(cfg.base_url, "https://gateway.example")

    def test_env_hostname_is_normalized(self):
        """A bare host from the environment still gets the https:// prefix."""
        cfg = extract_gateway_config(task_args={}, host_vars={}, env={"GATEWAY_HOSTNAME": "gw.example"})
        self.assertEqual(cfg.base_url, "https://gw.example")

    def test_missing_hostname_still_raises(self):
        with self.assertRaises(ValueError):
            extract_gateway_config(task_args={}, host_vars={}, env={}, required=True)

    def test_empty_env_value_is_ignored(self):
        """An exported-but-empty variable must not satisfy the requirement."""
        with self.assertRaises(ValueError):
            extract_gateway_config(task_args={}, host_vars={}, env={"GATEWAY_HOSTNAME": ""}, required=True)


class TestEnvPrecedence(unittest.TestCase):
    """task_args > host_vars > env, matching Ansible's own vars-before-env order."""

    def test_task_args_override_env(self):
        cfg = extract_gateway_config(
            task_args={"gateway_hostname": "https://task.example"},
            host_vars={},
            env={"GATEWAY_HOSTNAME": "https://env.example"},
        )
        self.assertEqual(cfg.base_url, "https://task.example")

    def test_host_vars_override_env(self):
        cfg = extract_gateway_config(
            task_args={},
            host_vars={"gateway_hostname": "https://inventory.example"},
            env={"GATEWAY_HOSTNAME": "https://env.example"},
        )
        self.assertEqual(cfg.base_url, "https://inventory.example")

    def test_env_fills_only_the_missing_parameter(self):
        """Mixed sources resolve independently per parameter."""
        cfg = extract_gateway_config(
            task_args={"gateway_username": "task-user"},
            host_vars={},
            env={"GATEWAY_HOSTNAME": "https://env.example", "GATEWAY_PASSWORD": "env-pass"},
        )
        self.assertEqual(cfg.base_url, "https://env.example")
        self.assertEqual(cfg.username, "task-user")
        self.assertEqual(cfg.password, "env-pass")


class TestCredentialsFromEnv(unittest.TestCase):
    """Username, password and token resolution."""

    def test_username_and_password_from_env(self):
        cfg = extract_gateway_config(
            task_args={},
            host_vars={},
            env={"GATEWAY_HOSTNAME": "https://gw.example", "GATEWAY_USERNAME": "admin", "GATEWAY_PASSWORD": "secret"},
        )
        self.assertEqual(cfg.username, "admin")
        self.assertEqual(cfg.password, "secret")

    def test_aap_username_and_password_from_env(self):
        cfg = extract_gateway_config(
            task_args={},
            host_vars={},
            env={"AAP_HOSTNAME": "https://gw.example", "AAP_USERNAME": "admin", "AAP_PASSWORD": "secret"},
        )
        self.assertEqual(cfg.username, "admin")
        self.assertEqual(cfg.password, "secret")

    def test_token_from_env(self):
        cfg = extract_gateway_config(
            task_args={},
            host_vars={},
            env={"GATEWAY_HOSTNAME": "https://gw.example", "GATEWAY_API_TOKEN": "tok123"},
        )
        self.assertEqual(cfg.oauth_token, "tok123")

    def test_env_token_does_not_override_explicit_credentials(self):
        """Mirrors the existing aap_token ansible_fact guard: a stale exported
        token must not hijack a task that supplies username and password."""
        cfg = extract_gateway_config(
            task_args={"gateway_hostname": "https://gw.example", "gateway_username": "admin", "gateway_password": "secret"},
            host_vars={},
            env={"GATEWAY_API_TOKEN": "tok123"},
        )
        self.assertIsNone(cfg.oauth_token)
        self.assertEqual(cfg.username, "admin")

    def test_env_username_does_not_suppress_inventory_token(self):
        """Regression: an exported GATEWAY_USERNAME must not discard the inventory
        aap_token fact.  The environment ranks below inventory, so suppressing the
        token would leave a username with no password and no token."""
        cfg = extract_gateway_config(
            task_args={},
            host_vars={"gateway_hostname": "https://gw.example", "aap_token": {"token": "host-tok", "id": 1}},
            env={"GATEWAY_USERNAME": "admin"},
        )
        self.assertEqual(cfg.oauth_token, "host-tok")

    def test_env_credentials_do_not_suppress_inventory_token(self):
        """Same guard with both username and password exported."""
        cfg = extract_gateway_config(
            task_args={},
            host_vars={"gateway_hostname": "https://gw.example", "aap_token": {"token": "host-tok", "id": 1}},
            env={"GATEWAY_USERNAME": "admin", "GATEWAY_PASSWORD": "secret"},
        )
        self.assertEqual(cfg.oauth_token, "host-tok")

    def test_task_credentials_still_suppress_inventory_token(self):
        """The original guard is preserved: explicit task credentials win over the fact."""
        cfg = extract_gateway_config(
            task_args={"gateway_username": "admin", "gateway_password": "secret"},
            host_vars={"gateway_hostname": "https://gw.example", "aap_token": {"token": "host-tok", "id": 1}},
            env={},
        )
        self.assertIsNone(cfg.oauth_token)

    def test_inventory_credentials_still_suppress_inventory_token(self):
        cfg = extract_gateway_config(
            task_args={},
            host_vars={
                "gateway_hostname": "https://gw.example",
                "gateway_username": "admin",
                "gateway_password": "secret",
                "aap_token": {"token": "host-tok", "id": 1},
            },
            env={},
        )
        self.assertIsNone(cfg.oauth_token)


class TestValidateCertsFromEnv(unittest.TestCase):
    """GATEWAY_VERIFY_SSL is a string: bool('false') is True, so it must be parsed."""

    def test_env_false_disables_verification(self):
        for raw in ("false", "False", "FALSE", "no", "off", "0", "f", " false "):
            with self.subTest(raw=raw):
                cfg = extract_gateway_config(
                    task_args={},
                    host_vars={},
                    env={"GATEWAY_HOSTNAME": "https://gw.example", "GATEWAY_VERIFY_SSL": raw},
                )
                self.assertFalse(cfg.verify_ssl, f"{raw!r} must disable SSL verification")

    def test_env_true_enables_verification(self):
        for raw in ("true", "True", "yes", "on", "1", "t"):
            with self.subTest(raw=raw):
                cfg = extract_gateway_config(
                    task_args={},
                    host_vars={},
                    env={"GATEWAY_HOSTNAME": "https://gw.example", "GATEWAY_VERIFY_SSL": raw},
                )
                self.assertTrue(cfg.verify_ssl)

    def test_aap_validate_certs_env_alias(self):
        cfg = extract_gateway_config(
            task_args={},
            host_vars={},
            env={"AAP_HOSTNAME": "https://gw.example", "AAP_VALIDATE_CERTS": "false"},
        )
        self.assertFalse(cfg.verify_ssl)

    def test_task_args_false_still_wins_over_env_true(self):
        """False from the task must not be dropped in favour of the environment."""
        cfg = extract_gateway_config(
            task_args={"gateway_hostname": "https://gw.example", "validate_certs": False},
            host_vars={},
            env={"GATEWAY_VERIFY_SSL": "true"},
        )
        self.assertFalse(cfg.verify_ssl)

    def test_host_vars_false_still_wins_over_env_true(self):
        cfg = extract_gateway_config(
            task_args={"gateway_hostname": "https://gw.example"},
            host_vars={"validate_certs": False},
            env={"GATEWAY_VERIFY_SSL": "true"},
        )
        self.assertFalse(cfg.verify_ssl)

    def test_default_is_true_when_unset(self):
        cfg = extract_gateway_config(task_args={"gateway_hostname": "https://gw.example"}, host_vars={}, env={})
        self.assertTrue(cfg.verify_ssl)

    def test_invalid_boolean_raises(self):
        with self.assertRaises(ValueError):
            extract_gateway_config(
                task_args={},
                host_vars={},
                env={"GATEWAY_HOSTNAME": "https://gw.example", "GATEWAY_VERIFY_SSL": "maybe"},
            )

    def test_invalid_env_boolean_is_not_parsed_when_task_overrides(self):
        """Regression: the environment value must only be parsed when it is used.
        An unparsable GATEWAY_VERIFY_SSL must not break a task that sets the value."""
        cfg = extract_gateway_config(
            task_args={"gateway_hostname": "https://gw.example", "validate_certs": False},
            host_vars={},
            env={"GATEWAY_VERIFY_SSL": "maybe"},
        )
        self.assertFalse(cfg.verify_ssl)

    def test_invalid_env_boolean_is_not_parsed_when_inventory_overrides(self):
        cfg = extract_gateway_config(
            task_args={},
            host_vars={"gateway_hostname": "https://gw.example", "aap_validate_certs": True},
            env={"GATEWAY_VERIFY_SSL": "maybe"},
        )
        self.assertTrue(cfg.verify_ssl)


class TestRequestTimeoutFromEnv(unittest.TestCase):
    """GATEWAY_REQUEST_TIMEOUT arrives as a string and must become a float."""

    def test_env_timeout_is_coerced_to_float(self):
        cfg = extract_gateway_config(
            task_args={},
            host_vars={},
            env={"GATEWAY_HOSTNAME": "https://gw.example", "GATEWAY_REQUEST_TIMEOUT": "30"},
        )
        self.assertEqual(cfg.request_timeout, 30.0)
        self.assertIsInstance(cfg.request_timeout, float)

    def test_aap_request_timeout_env_alias(self):
        cfg = extract_gateway_config(
            task_args={},
            host_vars={},
            env={"AAP_HOSTNAME": "https://gw.example", "AAP_REQUEST_TIMEOUT": "45.5"},
        )
        self.assertEqual(cfg.request_timeout, 45.5)

    def test_task_args_override_env_timeout(self):
        cfg = extract_gateway_config(
            task_args={"gateway_hostname": "https://gw.example", "request_timeout": 5.0},
            host_vars={},
            env={"GATEWAY_REQUEST_TIMEOUT": "30"},
        )
        self.assertEqual(cfg.request_timeout, 5.0)

    def test_default_timeout_when_unset(self):
        cfg = extract_gateway_config(task_args={"gateway_hostname": "https://gw.example"}, host_vars={}, env={})
        self.assertEqual(cfg.request_timeout, 10.0)


class TestEnvDefaultsToOsEnviron(unittest.TestCase):
    """When no env mapping is passed, os.environ is used."""

    def test_os_environ_is_the_default_source(self):
        os.environ["GATEWAY_HOSTNAME"] = "https://from-os-environ.example"
        try:
            cfg = extract_gateway_config(task_args={}, host_vars={})
            self.assertEqual(cfg.base_url, "https://from-os-environ.example")
        finally:
            del os.environ["GATEWAY_HOSTNAME"]

    def test_explicit_empty_env_ignores_os_environ(self):
        os.environ["GATEWAY_HOSTNAME"] = "https://from-os-environ.example"
        try:
            with self.assertRaises(ValueError):
                extract_gateway_config(task_args={}, host_vars={}, env={}, required=True)
        finally:
            del os.environ["GATEWAY_HOSTNAME"]


if __name__ == "__main__":
    unittest.main()
