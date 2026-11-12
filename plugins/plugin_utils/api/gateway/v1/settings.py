"""
API v1 Settings dataclass and transform mixin.

Settings uses a singleton endpoint (/settings/all/) rather than standard CRUD.
The mixin declares is_singleton=True so the framework handles find/update correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, SingletonMutationPlan, TransformContext


@dataclass
class APISettings_v1(BaseTransformMixin):
    """API v1 representation of gateway settings (flat key-value dict)."""

    settings: Optional[Dict[str, Any]] = None


class SettingsTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for Settings API v1.

    Settings is a singleton resource: GET /settings/all/ returns a flat dict,
    PUT /settings/all/ replaces values.  There is no list, create, or delete.
    """

    # Singleton flag — _find_resource and _update_resource check this
    is_singleton = True

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APISettings_v1:
        settings = getattr(ansible_instance, "settings", None)
        return APISettings_v1(settings=settings)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        # Only get/update are meaningful for the singleton settings resource.
        return {
            "get": EndpointOperation(
                path="/api/gateway/v1/settings/all/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/gateway/v1/settings/all/",
                method="PUT",
                fields=["settings"],
                required_for="update",
                order=1,
                flatten_body=True,  # Send the dict values as the body directly
            ),
        }

    @classmethod
    def validate_mutation(cls, ansible_data, context):
        """Gateway settings support updates of a mapping, without create/delete."""
        if context.operation != "update":
            raise ValueError("Gateway settings support only find and update operations")
        if ansible_data.settings is not None and not isinstance(ansible_data.settings, dict):
            raise ValueError("settings must be a mapping")

    @classmethod
    def plan_mutation(cls, ansible_data, current, context):
        """Compare only requested keys using the module's string comparison rule."""
        current_settings = current.get("settings") or {}
        requested = ansible_data.settings or {}
        changes = {key: value for key, value in requested.items() if str(current_settings.get(key)) != str(value)}
        result = {
            "changed": bool(changes),
            "old_values": {key: current_settings.get(key) for key in changes},
            "new_values": changes,
        }
        if not changes or context.check_mode:
            result["settings"] = current_settings
        return SingletonMutationPlan(["update"] if changes else [], result, APISettings_v1(settings=changes))

    @classmethod
    def get_lookup_field(cls) -> str:
        # Settings has no lookup field; the singleton path is used directly.
        return ""

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.settings import AnsibleSettings

        return AnsibleSettings(settings=api_data)
