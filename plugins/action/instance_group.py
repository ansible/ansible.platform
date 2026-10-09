#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.instance_group import AnsibleInstanceGroup


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "instance_group"
    MODEL_CLASS = AnsibleInstanceGroup

    _WRITE_ONLY_FIELDS = frozenset({"instances"})

    def run(self, tmp=None, task_vars=None):
        state = self._task.args.get("state", "present")

        instances = self._task.args.pop("instances", None)

        result = super().run(tmp, task_vars)
        if result.get("failed"):
            return result

        resource_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")

        if resource_id and state not in ("absent", "deleted", "exists") and instances is not None:
            if self._client.manage_associations(
                "instance_groups",
                resource_id,
                "instances",
                instances,
                "instances",
                "hostname",
                service="controller",
            ):
                result["changed"] = True

        return result
