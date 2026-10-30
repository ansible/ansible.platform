# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Transform mixin and API model for bulk_host_delete."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

BULK_HOST_DELETE_ENDPOINT = "/api/controller/v2/bulk/host_delete/"


@dataclass
class APIBulkHostDelete_v2(BaseTransformMixin):
    """API v2 representation of a bulk host delete request."""

    hosts: List[int] = field(default_factory=list)


class BulkHostDeleteTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for BulkHostDelete API v2.

    Bulk delete uses the SDK launch_resource() method with this transform's
    request body and endpoint metadata.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Optional[Union[TransformContext, Dict[str, Any]]] = None) -> "APIBulkHostDelete_v2":
        """Create API instance from Ansible dataclass."""
        return APIBulkHostDelete_v2(
            hosts=list(getattr(ansible_instance, "hosts", [])),
        )

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleBulkHostDelete":
        """Transform from API format to Ansible format."""
        from ....ansible_models.bulk_host_delete import AnsibleBulkHostDelete

        return AnsibleBulkHostDelete(
            hosts=api_data.get("hosts", []),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoint for bulk host delete."""
        return {
            "create": EndpointOperation(
                path=BULK_HOST_DELETE_ENDPOINT,
                method="POST",
                fields=["hosts"],
                required_for="create",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "hosts"
