"""
API v1 ProjectUpdate dataclass and transform mixin.

Handles transformations between Ansible format and the Controller API format
for launching a project update (sync).

Launching an update is a POST to an existing project's /update/ sub-action
endpoint, not a generic resource create — so the "create" and "get"
operations target two different Controller resource types:
  - create: POST /api/controller/v2/projects/{project_id}/update/
  - get (poll for completion): GET /api/controller/v2/project_updates/{id}/
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...ansible_models.project_update import AnsibleProjectUpdate
from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIProjectUpdate_v1:
    """Wire format for launching/polling a Controller project update."""

    project_id: Optional[int] = None
    id: Optional[int] = None
    status: Optional[str] = None
    finished: Optional[str] = None


class ProjectUpdateTransformMixin_v1(BaseTransformMixin):
    """Transforms between AnsibleProjectUpdate and APIProjectUpdate_v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance: AnsibleProjectUpdate, context: TransformContext) -> APIProjectUpdate_v1:
        """Forward: Ansible model -> API wire format.

        If ``ansible_instance.id`` is already set (a poll of an in-flight
        project_update, via _wait_for_resource_completion's replace()), reuse
        it directly for the "get" operation's {id} path param. Otherwise this
        is the initial launch: resolve the target project's id by name.
        """
        if ansible_instance.id is not None:
            return APIProjectUpdate_v1(id=ansible_instance.id)

        project_id = context.manager.lookup_resource_id("/api/controller/v2/projects/", "name", ansible_instance.name)
        if project_id is None:
            raise ValueError("Could not find project '%s'" % ansible_instance.name)

        return APIProjectUpdate_v1(project_id=project_id)

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: TransformContext) -> AnsibleProjectUpdate:
        """Reverse: API response (the launched/polled project_update) -> Ansible model."""
        return AnsibleProjectUpdate(
            id=api_data.get("id"),
            name=api_data.get("name", ""),
            status=api_data.get("status"),
            finished=api_data.get("finished"),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/projects/{project_id}/update/",
                method="POST",
                fields=[],
                path_params=["project_id"],
                required_for="create",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/controller/v2/project_updates/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"
