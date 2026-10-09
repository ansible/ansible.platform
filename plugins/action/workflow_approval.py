#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError

from .base_action import BaseResourceActionPlugin


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for workflow_approval — wait for and approve/deny a workflow approval node."""

    MODULE_NAME = "workflow_approval"
    MODEL_CLASS = None

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        doc = self._get_documentation()
        argspec = self._build_argspec_from_docs(doc) if doc else None
        if not argspec:
            raise AnsibleError("Could not load DOCUMENTATION for workflow_approval module")

        validated_input = self._validate_data(self._task.args.copy(), argspec, "input")
        validated_params = validated_input.validated_parameters

        workflow_job_id = validated_params["workflow_job_id"]
        name = validated_params["name"]
        action = validated_params.get("action", "approve")
        timeout = validated_params.get("timeout", 10)
        interval = validated_params.get("interval", 1)

        if self._task.check_mode:
            result.update(
                {
                    "changed": True,
                    "failed": False,
                    "msg": "Would %s workflow approval node '%s' in workflow job %d" % (action, name, workflow_job_id),
                }
            )
            return result

        manager, facts_to_set = self._get_or_spawn_manager(task_vars)
        self._client = manager
        if facts_to_set:
            result["ansible_facts"] = facts_to_set
            result["_ansible_facts_cacheable"] = True

        try:
            sdk_result = manager.approve_workflow_node(
                workflow_job_id=workflow_job_id,
                node_name=name,
                action=action,
                timeout=timeout,
                interval=interval,
            )
            result.update(
                {
                    "changed": sdk_result.get("changed", True),
                    "failed": False,
                    "workflow_approval": sdk_result,
                    **sdk_result,
                }
            )
        except ValueError as exc:
            result.update(
                {
                    "changed": False,
                    "failed": True,
                    "msg": str(exc),
                }
            )
        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in workflow_approval action plugin: %s" % exc)
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
