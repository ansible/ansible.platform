#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.instance import AnsibleInstance


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "instance"
    MODEL_CLASS = AnsibleInstance

    def _detect_operation(self, args: dict) -> str:
        state = args.get("state", "present")
        if state in ("absent", "deleted"):
            # Instances cannot be deleted — state=absent means deprovision.
            # Convert to an update that sets node_state=deprovisioning.
            args["node_state"] = "deprovisioning"
            args["state"] = "present"
            return "update" if args.get("id") else "create"
        return super()._detect_operation(args)
