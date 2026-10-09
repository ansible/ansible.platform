#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.bulk_host_create module.

Bulk host create is a non-idempotent POST operation: each call creates new hosts
in the specified inventory via /api/controller/v2/bulk/host_create/.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for bulk_host_create module."""

    MODULE_NAME = "bulk_host_create"

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

                raise AnsibleError("Could not load DOCUMENTATION for bulk_host_create module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            validated_params = validated_input.validated_parameters
            hosts = validated_params.get("hosts", [])
            inventory = validated_params.get("inventory")

            if not hosts:
                result.update(
                    {
                        "changed": False,
                        "failed": True,
                        "msg": "No hosts provided for bulk creation.",
                    }
                )
                return result

            if not inventory:
                result.update(
                    {
                        "changed": False,
                        "failed": True,
                        "msg": "Inventory is required for bulk host creation.",
                    }
                )
                return result

            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "failed": False,
                        self.MODULE_NAME: {
                            "inventory": inventory,
                            "host_count": len(hosts),
                        },
                    }
                )
                return result

            # Execute bulk host create via the manager pipeline
            ansible_data = {
                "hosts": hosts,
                "inventory": inventory,
            }

            manager_result = manager.execute(
                operation="create",
                module_name=self.MODULE_NAME,
                ansible_data=ansible_data,
            )

            result.update(
                {
                    "changed": True,
                    "failed": False,
                    self.MODULE_NAME: manager_result,
                }
            )

        except Exception as e:
            import traceback

            self._display.vvv("Error in bulk_host_create action plugin: %s" % e)
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
