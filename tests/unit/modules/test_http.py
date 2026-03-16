# (c) 2026 Red Hat Inc.
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import unittest
from unittest.mock import patch, MagicMock

from ansible_collections.ansible.platform.plugins.connection.http import Connection
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient


class TestHTTPConnectionDispatcher(unittest.TestCase):
    def setUp(self):
        self.mock_play_context = MagicMock()
        self.mock_play_context.shell = 'sh'
        self.mock_play_context.executable = None
        self.mock_new_stdin = MagicMock()
        self.connection = Connection(self.mock_play_context, self.mock_new_stdin)

    @patch('ansible_collections.ansible.platform.plugins.connection.http.Connection._get_direct_client')
    def test_get_client_direct_mode(self, mock_get_direct):
        """Validates that False routing hits the direct client logic."""
        self.connection.get_option = MagicMock(return_value=False)
        mock_direct_client = MagicMock(spec=ManagerRPCClient)
        mock_get_direct.return_value = (mock_direct_client, None)
        client, facts = self.connection.get_client(task_vars={}, gateway_config=MagicMock())
        mock_get_direct.assert_called_once()
        self.assertEqual(client, mock_direct_client)

    @patch('ansible_collections.ansible.platform.plugins.connection.http.Connection._get_persistent_client')
    def test_get_client_persistent_mode(self, mock_get_persistent):
        """Validates that True routing hits the persistent connection logic."""
        self.connection.get_option = MagicMock(return_value=True)
        mock_persistent_client = MagicMock(spec=ManagerRPCClient)
        mock_get_persistent.return_value = (mock_persistent_client, {'fact': 'value'})
        client, facts = self.connection.get_client(task_vars={}, gateway_config=MagicMock())
        mock_get_persistent.assert_called_once()
        self.assertEqual(client, mock_persistent_client)


if __name__ == '__main__':
    unittest.main()
