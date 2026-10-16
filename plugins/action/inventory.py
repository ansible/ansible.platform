#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.inventory import AnsibleInventory


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "inventory"
    MODEL_CLASS = AnsibleInventory

    def _resolve_lookup(self, resource, resource_data, validated_params):
        """Normalize numeric organization IDs to names for state comparison.

        The API reverse transform exposes the organization name so name-based
        task input compares idempotently. Resolve numeric task input to that
        same name before the lookup and write operations.
        """
        organization = getattr(resource, "organization", None)
        if organization is not None and str(organization).strip().isdigit():
            names = self._client.lookup_organization_names([int(organization)])
            if names:
                resource.organization = names[0]
                resource_data["organization"] = names[0]
