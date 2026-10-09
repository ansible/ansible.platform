"""
API controller v2 JobList transform mixin.

job_list is a read-only module that queries /api/controller/v2/jobs/.
It uses search_api() directly rather than the CRUD execute() pipeline,
so only list endpoint operations are defined.
"""

from __future__ import annotations

from typing import Any, Dict

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation


class JobListTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for Controller Jobs listing API v2."""

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "list": EndpointOperation(
                path="/api/controller/v2/jobs/",
                method="GET",
                fields=["status", "page"],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "id"

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Any,
    ):
        from ....ansible_models.job_list import AnsibleJobList

        return AnsibleJobList(
            status=api_data.get("status"),
        )
