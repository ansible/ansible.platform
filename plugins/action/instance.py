#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.instance import AnsibleInstance


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "instance"
    MODEL_CLASS = AnsibleInstance

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        state = self._task.args.get("state", "present")

        if state in ("absent", "deleted"):
            # Instances cannot be deleted via the API — state=absent triggers
            # deprovisioning by PATCHing node_state=deprovisioning.
            # First check if the instance exists; if not, treat as already absent.
            self._task.args["state"] = "exists"
            result = super().run(tmp, task_vars)
            if result.get("failed"):
                return result
            if not result.get("exists", False):
                return {
                    "changed": False,
                    "msg": "Instance does not exist (already absent)",
                    "instance": {"state": "absent"},
                }
            # Instance exists — update with deprovisioning.
            self._task.args["state"] = "present"
            self._task.args["node_state"] = "deprovisioning"

        return super().run(tmp, task_vars)
