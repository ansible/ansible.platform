"""API v1 Rulebook Activation Copy dataclass and transform mixin."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIRulebookActivationCopy_v1(BaseTransformMixin):
    """API v1 representation of a rulebook activation copy operation."""

    name: Optional[str] = None

    # Read-only fields from API
    id: Optional[int] = None


class RulebookActivationCopyTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for Rulebook Activation Copy API v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIRulebookActivationCopy_v1":
        """Create API instance from Ansible dataclass."""
        api_data = {}

        name = getattr(ansible_instance, "name", None)
        if name is not None:
            api_data["name"] = name

        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIRulebookActivationCopy_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for rulebook activation copy operations."""
        return {
            "list": EndpointOperation(
                path="/api/eda/v1/activations/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleRulebookActivationCopy":
        """Transform from API format to Ansible format."""
        from ....ansible_models.rulebook_activation_copy import AnsibleRulebookActivationCopy

        ansible_data = {
            "name": api_data.get("name", ""),
            "id": api_data.get("id"),
        }
        return AnsibleRulebookActivationCopy(**ansible_data)
