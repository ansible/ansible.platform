# (c) 2026 Red Hat Inc.
#
# This file is part of Ansible
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the platform connection plugin (AAP-67324: persistent vs direct mode).

Run with pytest (from collection root; requires ansible-core installed):
  pytest tests/unit/plugins/connection/test_http.py -v

Or with tox-ansible (recommended for CI / version matrix):
  tox -f unit --ansible -p auto --conf tox-ansible.ini

Covers:
- get_client() dispatcher: routes to _get_direct_client (direct/ephemeral) or _get_persistent_client
  based on connection option 'persistent' or variables ansible_platform_use_persistent_connection /
  ansible_platform_persistent.
- Direct mode: returns (client, None); no facts stored.
- Persistent mode: returns (client, facts_dict) with platform_manager_socket and platform_manager_authkey.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import unittest
from unittest.mock import patch, MagicMock

from ansible_collections.ansible.platform.plugins.connection.http import Connection
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient


class TestHTTPConnectionDispatcher(unittest.TestCase):
    def setUp(self):
        """Set up the mock connection object and standard variables for testing."""
        self.mock_play_context = MagicMock()
        self.mock_play_context.shell = 'sh'
        self.mock_play_context.executable = '/bin/sh'
        self.mock_new_stdin = MagicMock()
        self.connection = Connection(self.mock_play_context, self.mock_new_stdin)
        self.connection._connected = True
        self.gateway_config = GatewayConfig(base_url="https://example.com/", username="admin", password="secret")
        self.task_vars = {"inventory_hostname": "localhost"}

    def test_get_client_default_uses_direct_mode(self):
        """When persistent option is not set (or False), get_client routes to _get_direct_client."""
        mock_direct = MagicMock(return_value=(MagicMock(), None))
        mock_persistent = MagicMock()

        with patch.object(self.connection, "get_option", side_effect=KeyError("persistent")):
            with patch.object(self.connection, "_get_direct_client", mock_direct):
                with patch.object(self.connection, "_get_persistent_client", mock_persistent):
                    client, facts = self.connection.get_client(self.task_vars, self.gateway_config)

        mock_direct.assert_called_once_with(self.task_vars, self.gateway_config)
        mock_persistent.assert_not_called()
        self.assertIsNone(facts)

    def test_get_client_persistent_option_true_routes_to_persistent(self):
        """When connection option persistent=True, get_client routes to _get_persistent_client."""
        mock_client = MagicMock()
        mock_facts = {"platform_manager_socket": "/tmp/sock", "platform_manager_authkey": "key"}
        mock_direct = MagicMock()
        mock_persistent = MagicMock(return_value=(mock_client, mock_facts))

        with patch.object(self.connection, "get_option", return_value=True):
            with patch.object(self.connection, "_get_direct_client", mock_direct):
                with patch.object(self.connection, "_get_persistent_client", mock_persistent):
                    client, facts = self.connection.get_client(self.task_vars, self.gateway_config)

        mock_persistent.assert_called_once_with(self.task_vars, self.gateway_config)
        mock_direct.assert_not_called()
        self.assertIs(client, mock_client)
        self.assertEqual(facts, mock_facts)

    def test_get_client_persistent_option_false_routes_to_direct(self):
        """When connection option persistent=False, get_client routes to _get_direct_client."""
        mock_direct = MagicMock(return_value=(MagicMock(), None))
        mock_persistent = MagicMock()

        with patch.object(self.connection, "get_option", return_value=False):
            with patch.object(self.connection, "_get_direct_client", mock_direct):
                with patch.object(self.connection, "_get_persistent_client", mock_persistent):
                    client, facts = self.connection.get_client(self.task_vars, self.gateway_config)

        mock_direct.assert_called_once_with(self.task_vars, self.gateway_config)
        mock_persistent.assert_not_called()
        self.assertIsNone(facts)

    def test_get_client_var_ansible_platform_use_persistent_connection_true(self):
        """When get_option is missing and task_vars has ansible_platform_use_persistent_connection=true, use persistent."""
        self.task_vars["ansible_platform_use_persistent_connection"] = True
        self.task_vars["hostvars"] = {"localhost": {}}
        mock_persistent = MagicMock(return_value=(MagicMock(), {"platform_manager_socket": "/tmp/s"}))

        with patch.object(self.connection, "get_option", side_effect=KeyError("persistent")):
            with patch.object(self.connection, "_get_direct_client", MagicMock()):
                with patch.object(self.connection, "_get_persistent_client", mock_persistent):
                    self.connection.get_client(self.task_vars, self.gateway_config)

        mock_persistent.assert_called_once()

    def test_get_client_var_ansible_platform_persistent_true(self):
        """When get_option is missing and task_vars has ansible_platform_persistent=true, use persistent."""
        self.task_vars["ansible_platform_persistent"] = "true"
        self.task_vars["hostvars"] = {"localhost": {}}
        mock_persistent = MagicMock(return_value=(MagicMock(), {}))

        with patch.object(self.connection, "get_option", side_effect=KeyError("persistent")):
            with patch.object(self.connection, "_get_direct_client", MagicMock()):
                with patch.object(self.connection, "_get_persistent_client", mock_persistent):
                    self.connection.get_client(self.task_vars, self.gateway_config)

        mock_persistent.assert_called_once()

    def test_get_client_var_hostvars_ansible_platform_use_persistent_connection(self):
        """When hostvars[host] has ansible_platform_use_persistent_connection=yes, use persistent."""
        self.task_vars = {
            "inventory_hostname": "myhost",
            "hostvars": {"myhost": {"ansible_platform_use_persistent_connection": "yes"}},
        }
        mock_persistent = MagicMock(return_value=(MagicMock(), {}))

        with patch.object(self.connection, "get_option", side_effect=KeyError("persistent")):
            with patch.object(self.connection, "_get_direct_client", MagicMock()):
                with patch.object(self.connection, "_get_persistent_client", mock_persistent):
                    self.connection.get_client(self.task_vars, self.gateway_config)

        mock_persistent.assert_called_once()

    def test_get_client_var_falsy_uses_direct(self):
        """When vars set persistent to false/no/0, use direct mode."""
        self.task_vars["ansible_platform_persistent"] = "false"
        self.task_vars["hostvars"] = {"localhost": {}}
        mock_direct = MagicMock(return_value=(MagicMock(), None))

        with patch.object(self.connection, "get_option", side_effect=KeyError("persistent")):
            with patch.object(self.connection, "_get_direct_client", mock_direct):
                with patch.object(self.connection, "_get_persistent_client", MagicMock()):
                    self.connection.get_client(self.task_vars, self.gateway_config)

        mock_direct.assert_called_once()


if __name__ == '__main__':
    unittest.main()
