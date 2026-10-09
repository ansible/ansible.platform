#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for job_cancel module.

Cancels a Controller job by POSTing to its /cancel/ sub-endpoint.
Already-finished jobs are a safe no-op (changed=False) unless
fail_if_not_running is True.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from typing import Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.job_cancel import AnsibleJobCancel


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "job_cancel"
    MODEL_CLASS = AnsibleJobCancel
    LOOKUP_FIELD = "job_id"

    def run(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """Cancel a Controller job via the SDK cancel_resource() method.

        This overrides the standard CRUD run() because cancel is a
        Shape 4 operation (POST to /cancel/ sub-endpoint), not a
        standard create/update/delete.
        """
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            job_id = validated_params.get("job_id")
            fail_if_not_running = validated_params.get("fail_if_not_running", False)

            if not job_id:
                raise AnsibleError("job_id is required")

            # Check mode: report would-change without touching the API
            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "id": job_id,
                        "status": "cancel would be attempted (check mode)",
                    }
                )
                return result

            # Call the SDK cancel_resource() method
            cancel_result = manager.cancel_resource(
                resource_id=job_id,
                cancel_endpoint_path="jobs",
                fail_if_not_running=fail_if_not_running,
                service="controller",
            )

            result.update(cancel_result)

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
