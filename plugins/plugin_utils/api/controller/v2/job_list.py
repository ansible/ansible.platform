"""
API v2 JobList dataclass and transform mixin.

JobList queries the controller jobs endpoint with optional filters.
There is no standard CRUD lifecycle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union
from urllib.parse import urljoin

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIJobList_v2(BaseTransformMixin):
    """API v2 representation of a job list query."""

    status: Optional[str] = None
    page: Optional[int] = None
    all_pages: bool = False
    query: Optional[Dict] = None


class JobListTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for JobList API v2."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIJobList_v2:
        return APIJobList_v2(
            status=getattr(ansible_instance, "status", None),
            page=getattr(ansible_instance, "page", None),
            all_pages=getattr(ansible_instance, "all_pages", False),
            query=getattr(ansible_instance, "query", None),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "list": EndpointOperation(
                path="/api/controller/v2/jobs/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return ""

    @classmethod
    def resolve(cls, ansible_instance, context: TransformContext) -> dict:
        """List jobs from the controller API with optional filters."""
        status = getattr(ansible_instance, "status", None)
        page = getattr(ansible_instance, "page", None)
        all_pages = getattr(ansible_instance, "all_pages", False)
        query = getattr(ansible_instance, "query", None) or {}

        params = {}
        if status:
            params["status"] = status
        if page:
            params["page"] = page
        params.update(query)

        url = context.manager._build_url(
            "/api/controller/v2/jobs/",
            service="controller",
            api_version=context.api_version,
        )

        response = context.manager._make_request(
            "get", url, operation="job_list", resource="jobs", params=params
        )
        data = response.json()

        if all_pages and "results" in data:
            results = list(data.get("results", []))
            next_url = data.get("next")
            while next_url:
                abs_url = urljoin(context.manager.base_url, next_url)
                next_resp = context.manager._make_request(
                    "get", abs_url, operation="job_list_paginate", resource="jobs"
                )
                next_data = next_resp.json()
                results.extend(next_data.get("results", []))
                next_url = next_data.get("next")
            data["results"] = results
            data["next"] = None

        data["changed"] = False
        return data

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.job_list import AnsibleJobList

        return AnsibleJobList()
