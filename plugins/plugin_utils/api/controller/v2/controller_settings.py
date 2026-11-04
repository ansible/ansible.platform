"""Controller API v2 transform for the settings singleton."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

SETTINGS_ENDPOINT = "/api/controller/v2/settings/all/"


@dataclass
class APIControllerSettings_v2(BaseTransformMixin):
    """Wire representation of the flat Controller ``settings/all`` response."""

    settings: Optional[Dict[str, Any]] = None


class ControllerSettingsTransformMixin_v2(BaseTransformMixin):
    """Transform Controller settings to and from the Ansible representation."""

    # Controller settings is a singleton: only GET and PATCH are supported.
    is_singleton = True

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIControllerSettings_v2:
        return APIControllerSettings_v2(settings=getattr(ansible_instance, "settings", None))

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "get": EndpointOperation(
                path=SETTINGS_ENDPOINT,
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
            "update": EndpointOperation(
                path=SETTINGS_ENDPOINT,
                method="PATCH",
                fields=["settings"],
                required_for="update",
                order=1,
                flatten_body=True,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        # The endpoint represents one fixed settings collection and has no ID.
        return ""

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.controller_settings import AnsibleControllerSettings

        return AnsibleControllerSettings(settings=api_data or {})
