#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.token module.

Tokens are non-idempotent: each 'present' call creates a new token via
manager.execute('create').  Delete uses existing_token_id or existing_token['id']
via manager.execute('delete').  Sets ansible_facts.aap_token with created token data.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.token import AnsibleToken


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for token module."""

    MODULE_NAME = "token"

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

                raise AnsibleError("Could not load DOCUMENTATION for token module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            validated_params = validated_input.validated_parameters
            state = validated_params.get("state", "present")

            if state == "absent":
                # Delete token by id (from existing_token or existing_token_id)
                token_id = None
                existing_token = validated_params.get("existing_token")
                existing_token_id = validated_params.get("existing_token_id")

                if existing_token_id is not None:
                    token_id = int(existing_token_id)
                elif existing_token and isinstance(existing_token, dict):
                    token_id = existing_token.get("id")

                if token_id is None:
                    result.update(
                        {
                            "changed": False,
                            "failed": False,
                            self.MODULE_NAME: {"state": "absent"},
                            "msg": "No token id provided for deletion.",
                        }
                    )
                    return result

                if self._task.check_mode:
                    result.update(
                        {
                            "changed": True,
                            "failed": False,
                            self.MODULE_NAME: {"state": "absent", "id": token_id},
                        }
                    )
                    return result

                try:
                    token_data = {"id": token_id}
                    manager.execute(
                        operation="delete",
                        module_name=self.MODULE_NAME,
                        ansible_data=token_data,
                    )
                    result.update(
                        {
                            "changed": True,
                            "failed": False,
                            self.MODULE_NAME: {"state": "absent", "id": token_id},
                        }
                    )
                except Exception as e:
                    if "404" in str(e) or "not found" in str(e).lower():
                        result.update(
                            {
                                "changed": False,
                                "failed": False,
                                self.MODULE_NAME: {"state": "absent"},
                                "msg": "Token %s already absent." % token_id,
                            }
                        )
                    else:
                        raise

            else:
                # state == 'present': create a new token (always creates, never idempotent)
                token_obj_data = {}
                for field in ("description", "application", "organization"):
                    val = validated_params.get(field)
                    if val is not None:
                        token_obj_data[field] = val

                # scope is type:list in argspec but the gateway API expects a
                # space-separated string (e.g. "read write").  Join here so the
                # AnsibleToken dataclass and the API both receive a str.
                scope = validated_params.get("scope")
                if scope is not None:
                    token_obj_data["scope"] = " ".join(scope) if isinstance(scope, list) else scope

                token = AnsibleToken(**token_obj_data)

                if self._task.check_mode:
                    result.update(
                        {
                            "changed": True,
                            "failed": False,
                            self.MODULE_NAME: {"state": "present"},
                            "ansible_facts": {"aap_token": {}},
                            "_ansible_facts_cacheable": False,
                        }
                    )
                    return result

                manager_result = manager.execute(
                    operation="create",
                    module_name=self.MODULE_NAME,
                    ansible_data=asdict(token),
                )

                # Set ansible fact so the token value is accessible in the play
                aap_token = {
                    "id": manager_result.get("id"),
                    "token": manager_result.get("token"),
                    "description": manager_result.get("description"),
                    "scope": manager_result.get("scope"),
                    "created": manager_result.get("created"),
                    "modified": manager_result.get("modified"),
                    "url": manager_result.get("url"),
                }

                # Flat top-level keys kept for backward compatibility with
                # playbooks written against <=2.6.
                _flat_strip = {"state", "changed", "failed"}
                flat_keys = {k: v for k, v in manager_result.items() if k not in _flat_strip}

                result.update(
                    {
                        "changed": True,
                        "failed": False,
                        self.MODULE_NAME: manager_result,
                        **flat_keys,
                        "ansible_facts": {"aap_token": aap_token},
                        "_ansible_facts_cacheable": False,
                    }
                )

        except Exception as e:
            import traceback

            self._display.vvv("Error in token action plugin: %s" % e)
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
