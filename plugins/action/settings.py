#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.settings module.

Settings is a singleton resource: manager.execute('find') reads the current state,
manager.execute('update') patches only the changed keys.  Idempotency is handled
at the action plugin level by comparing desired vs current values.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.settings import AnsibleSettings


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for settings module."""

    MODULE_NAME = "settings"

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                from ansible.errors import AnsibleError

                raise AnsibleError("Could not load DOCUMENTATION for settings module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            validated_params = validated_input.validated_parameters
            desired_settings = validated_params.get("settings", {}) or {}

            # GET current settings via manager.execute('find')
            current_result = manager.execute(
                operation="find",
                module_name=self.MODULE_NAME,
                ansible_data={"settings": {}},
            )
            current_settings = current_result.get("settings", {}) or {}

            # Idempotency: check which desired keys differ from current
            to_update = {k: v for k, v in desired_settings.items() if str(current_settings.get(k)) != str(v)}

            if not to_update:
                # Nothing to change
                result.update(
                    {
                        "changed": False,
                        "failed": False,
                        self.MODULE_NAME: {
                            "settings": current_settings,
                            "old_values": {},
                            "new_values": {},
                            "changed": False,
                        },
                    }
                )
                return result

            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "failed": False,
                        self.MODULE_NAME: {
                            "settings": current_settings,
                            "old_values": {k: current_settings.get(k) for k in to_update},
                            "new_values": to_update,
                            "changed": True,
                        },
                    }
                )
                return result

            # PATCH only the changed keys via manager.execute('update')
            update_settings = AnsibleSettings(settings=to_update)
            update_result = manager.execute(
                operation="update",
                module_name=self.MODULE_NAME,
                ansible_data=asdict(update_settings),
            )
            updated_settings = update_result.get("settings", {}) or {}

            result.update(
                {
                    "changed": True,
                    "failed": False,
                    self.MODULE_NAME: {
                        "settings": updated_settings,
                        "old_values": {k: current_settings.get(k) for k in to_update},
                        "new_values": to_update,
                        "changed": True,
                    },
                }
            )

        except Exception as e:
            import traceback

            self._display.vvv("Error in settings action plugin: %s" % e)
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
