"""Controller API v2 transform for the settings singleton."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

import yaml

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, SingletonMutationPlan, TransformContext

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
        name = getattr(ansible_instance, "name", None)
        if name is not None:
            settings = {name: cls.coerce_value(ansible_instance.value)}
        else:
            settings = ansible_instance.settings
        return APIControllerSettings_v2(settings=settings)

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

    @staticmethod
    def coerce_value(value):
        """Preserve legacy name/value conversion without exposing YAML contents."""
        if value is None or not isinstance(value, str):
            return value
        if (value.startswith("{") and value.endswith("}")) or (value.startswith("[") and value.endswith("]")):
            try:
                return yaml.safe_load(value)
            except yaml.YAMLError as exc:
                mark = getattr(exc, "problem_mark", None)
                if mark is not None:
                    message = "Unable to parse setting value as YAML at line %d, column %d" % (mark.line + 1, mark.column + 1)
                else:
                    message = "Unable to parse setting value as YAML"
            raise ValueError(message)
        if value.lower() in ("true", "false", "t", "f"):
            return value.lower() in ("true", "t")
        try:
            return int(value)
        except ValueError:
            return value

    @classmethod
    def validate_mutation(cls, ansible_data, context):
        """Require a supported operation and exactly one documented input form."""
        if context.operation != "update":
            raise ValueError("Controller settings support only find and update operations")
        if (ansible_data.name is None) == (ansible_data.settings is None):
            raise ValueError("Exactly one of name or settings is required")
        if ansible_data.name is not None:
            if not isinstance(ansible_data.name, str):
                raise ValueError("name must be a string")
            if ansible_data.value is None:
                raise ValueError("value is required when name is provided")
        elif not isinstance(ansible_data.settings, dict):
            raise ValueError("settings must be a mapping")

    @classmethod
    def plan_mutation(cls, ansible_data, current, context):
        """Validate setting names and plan a partial update with legacy results."""
        current_settings = current.get("settings") or {}
        requested = cls.from_ansible_data(ansible_data, context).settings
        unknown = sorted(set(requested) - set(current_settings))
        if unknown:
            raise ValueError("Unknown Controller setting(s): %s" % ", ".join(unknown))
        changes = {key: value for key, value in requested.items() if current_settings[key] != value}
        result = {
            "changed": bool(changes),
            "old_values": {key: current_settings[key] for key in requested},
            "new_values": requested,
            "diff": {
                "before": {key: current_settings[key] for key in changes},
                "after": changes,
            },
        }
        if not changes or context.check_mode:
            result["settings"] = current_settings
        return SingletonMutationPlan(["update"] if changes else [], result, APIControllerSettings_v2(settings=changes))

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
