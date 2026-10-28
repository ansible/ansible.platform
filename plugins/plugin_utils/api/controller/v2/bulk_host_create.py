"""
API v2 Bulk Host Create dataclass.

This is a Shape 5 (bulk) module: array-in/array-out with partial-failure
semantics. It does NOT use the standard CRUD endpoint operations; the
action plugin calls the SDK bulk_host_create() method directly.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class APIBulkHostCreate_v2:
    """API v2 representation of a bulk host create request."""

    hosts: List[dict] = field(default_factory=list)
    inventory: Optional[str] = None
