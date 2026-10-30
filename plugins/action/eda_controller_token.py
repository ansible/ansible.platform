#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.eda_controller_token module.

EDA controller tokens (AWX tokens) do not support PATCH — the API only
supports GET, POST (create), and DELETE.  When state=present and the token
already exists, the plugin deletes the existing token and creates a new one.
This always reports changed=True when an existing token is found.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.eda_controller_token import AnsibleEdaControllerToken


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for eda_controller_token module."""

    MODULE_NAME = "eda_controller_token"
    # Not consumed by run() (Shape 6 bypasses base class), kept for documentation.
    MODEL_CLASS = AnsibleEdaControllerToken
    _WRITE_ONLY_FIELDS = frozenset({"token"})
    _NO_LOG_FIELDS = frozenset({"token"})

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

                raise AnsibleError("Could not load DOCUMENTATION for %s module" % self.MODULE_NAME)

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            validated_params = validated_input.validated_parameters
            state = validated_params.get("state", "present")
            name = validated_params.get("name")
            description = validated_params.get("description")
            token_value = validated_params.get("token")

            # Find existing token by name
            existing = None
            try:
                find_result = manager.execute(
                    operation="find",
                    module_name=self.MODULE_NAME,
                    ansible_data={"name": name},
                )
                if find_result and find_result.get("id"):
                    existing = find_result
            except ValueError as e:
                if "not found" not in str(e).lower() and "404" not in str(e):
                    raise

            if state == "absent":
                if not existing:
                    result.update(
                        {
                            "changed": False,
                            "failed": False,
                            self.MODULE_NAME: {"state": "absent"},
                            "msg": "%s '%s' does not exist (already absent)" % (self.MODULE_NAME, name),
                        }
                    )
                    return result

                if self._task.check_mode:
                    result.update(
                        {
                            "changed": True,
                            "failed": False,
                            self.MODULE_NAME: {"state": "absent", "id": existing["id"]},
                        }
                    )
                    return result

                manager.execute(
                    operation="delete",
                    module_name=self.MODULE_NAME,
                    ansible_data={"id": existing["id"], "name": name},
                )
                result.update(
                    {
                        "changed": True,
                        "failed": False,
                        self.MODULE_NAME: {"state": "absent", "id": existing["id"]},
                    }
                )
                return result

            # state == "present"
            if token_value is None:
                from ansible.errors import AnsibleError

                raise AnsibleError("Parameter 'token' is required when state is 'present'")

            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "failed": False,
                        self.MODULE_NAME: {"name": name, "state": "present"},
                    }
                )
                return result

            # Delete existing token first (API does not support PATCH)
            if existing:
                manager.execute(
                    operation="delete",
                    module_name=self.MODULE_NAME,
                    ansible_data={"id": existing["id"], "name": name},
                )

            # Create new token
            token_data = {"name": name}
            if description is not None:
                token_data["description"] = description
            if token_value is not None:
                token_data["token"] = token_value

            token_obj = AnsibleEdaControllerToken(**token_data)
            create_result = manager.execute(
                operation="create",
                module_name=self.MODULE_NAME,
                ansible_data=asdict(token_obj),
            )

            result.update(
                {
                    "changed": True,
                    "failed": False,
                    self.MODULE_NAME: create_result,
                    "id": create_result.get("id"),
                }
            )

        except Exception as e:
            import traceback

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, e))
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
