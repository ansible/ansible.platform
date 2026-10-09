"""
Controller API v2 Job List transform mixin.

Minimal transform for the read-only job list query.
The action plugin uses search_api() directly, so no CRUD
endpoint operations are needed.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

CONTROLLER_JOBS_ENDPOINT = "/api/controller/v2/jobs/"


def build_query_params(ansible_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build query parameters from validated Ansible input.

    Merges status, page, and arbitrary query dict into a single
    dict suitable for passing to ``search_api()``.

    Args:
        ansible_data: Validated module parameters.

    Returns:
        Dict of query parameters for the Controller jobs API.
    """
    params: Dict[str, Any] = {}

    status = ansible_data.get("status")
    if status:
        params["status"] = status

    page = ansible_data.get("page")
    if page is not None:
        params["page"] = page

    query = ansible_data.get("query")
    if query:
        params.update(query)

    return params
