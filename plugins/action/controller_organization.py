from __future__ import absolute_import, division, print_function

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_organization import AnsibleControllerOrganization


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "controller_organization"
    MODEL_CLASS = AnsibleControllerOrganization

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        if result.get("failed"):
            return result
        state = self._task.args.get("state", "present")
        if state in ("absent", "deleted", "exists"):
            return result
        resource_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")
        if not resource_id:
            return result
        manager = self._client
        for field, endpoint in (("galaxy_credentials", "credentials"), ("instance_groups", "instance_groups")):
            desired = self._task.args.get(field)
            if desired is not None and manager.manage_associations(
                "organizations", resource_id, field, desired, endpoint, "name", service="controller", check_mode=self._task.check_mode
            ):
                result["changed"] = True
        return result
