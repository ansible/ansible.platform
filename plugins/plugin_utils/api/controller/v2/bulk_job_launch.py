# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Transform mixin and API model for bulk_job_launch."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

BULK_JOB_LAUNCH_ENDPOINT = "/api/controller/v2/bulk/job_launch/"


@dataclass
class APIBulkJobLaunch_v2(BaseTransformMixin):
    """API v2 representation of a bulk job launch request."""

    jobs: List[Dict] = field(default_factory=list)
    name: Optional[str] = None
    description: Optional[str] = None
    organization: Optional[int] = None
    inventory: Optional[int] = None
    limit: Optional[str] = None
    scm_branch: Optional[str] = None
    extra_vars: Optional[Dict] = None
    job_tags: Optional[str] = None
    skip_tags: Optional[str] = None


class BulkJobLaunchTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for BulkJobLaunch API v2."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIBulkJobLaunch_v2":
        """Create API instance from Ansible dataclass."""
        return APIBulkJobLaunch_v2(
            jobs=list(getattr(ansible_instance, "jobs", [])),
            name=getattr(ansible_instance, "name", None),
            description=getattr(ansible_instance, "description", None),
            limit=getattr(ansible_instance, "limit", None),
            scm_branch=getattr(ansible_instance, "scm_branch", None),
            extra_vars=getattr(ansible_instance, "extra_vars", None),
            job_tags=getattr(ansible_instance, "job_tags", None),
            skip_tags=getattr(ansible_instance, "skip_tags", None),
        )

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleBulkJobLaunch":
        """Transform from API format to Ansible format."""
        from ....ansible_models.bulk_job_launch import AnsibleBulkJobLaunch

        return AnsibleBulkJobLaunch(
            jobs=api_data.get("jobs", []),
            name=api_data.get("name"),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoint for bulk job launch."""
        return {
            "create": EndpointOperation(
                path=BULK_JOB_LAUNCH_ENDPOINT,
                method="POST",
                fields=[],
                required_for="create",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "jobs"
