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

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry import APIVersionRegistry
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.loader import DynamicClassLoader

class TestUserModule(unittest.TestCase):

    def test_filesystem_version_discovery_and_loading(self):
        """
        Validates APIVersionRegistry correctly scans the filesystem for versions,
        and DynamicClassLoader routes to the correct user module classes.
        """
        registry = APIVersionRegistry()
        supported = registry.get_supported_versions()
        self.assertIn('2', supported)
        self.assertTrue(len(supported) >= 1)

        latest = registry.get_latest_version()
        self.assertIsNotNone(latest)
        loader = DynamicClassLoader(registry)

        AnsibleClass, APIClass, MixinClass = loader.load_classes_for_module('user', '2')
        self.assertEqual(APIClass.__name__, 'APIUser_v2')
        self.assertEqual(AnsibleClass.__name__, 'AnsibleUser')
        self.assertTrue(hasattr(MixinClass, 'get_endpoint_operations'))

if __name__ == '__main__':
    unittest.main()