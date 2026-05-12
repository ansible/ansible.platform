"""
API v1 FeatureFlag dataclass and transform mixin.

The Gateway spec exposes feature flags at two endpoints:
  GET  /api/gateway/v1/feature_flags/           — list all flags
  GET  /api/gateway/v1/feature_flags/{id}/      — detail
  PATCH /api/gateway/v1/feature_flags/{id}/     — update (field: value)

There is also a read-only state endpoint /feature_flags_state/ but that
is not used here; the writable CRUD endpoint is /feature_flags/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext


@dataclass
class APIFeatureFlag_v1(BaseTransformMixin):
    """API v1 representation of a gateway feature flag."""

    name: Optional[str] = None

    value: Optional[str] = None
    id: Optional[int] = None
    ui_name: Optional[str] = None
    condition: Optional[str] = None
    required: Optional[bool] = None
    support_level: Optional[str] = None
    visibility: Optional[bool] = None
    toggle_type: Optional[str] = None
    description: Optional[str] = None
    support_url: Optional[str] = None
    labels: Optional[List[str]] = None


class FeatureFlagTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for FeatureFlag API v1."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIFeatureFlag_v1:
        api_data: Dict[str, Any] = {}

        name = getattr(ansible_instance, "name", None)
        if name is not None:
            api_data["name"] = str(name)

        value = getattr(ansible_instance, "value", None)
        if value is not None:
            api_data["value"] = value

        for ro in ("id",):
            val = getattr(ansible_instance, ro, None)
            if val is not None:
                api_data[ro] = val

        return APIFeatureFlag_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "list": EndpointOperation(
                path="/api/gateway/v1/feature_flags/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/gateway/v1/feature_flags/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/gateway/v1/feature_flags/{id}/",
                method="PATCH",
                fields=["value"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ...ansible_models.feature_flag import AnsibleFeatureFlag

        return AnsibleFeatureFlag(
            name=api_data.get("name", ""),
            value=api_data.get("value"),
            id=api_data.get("id"),
            ui_name=api_data.get("ui_name"),
            condition=api_data.get("condition"),
            required=api_data.get("required"),
            support_level=api_data.get("support_level"),
            visibility=api_data.get("visibility"),
            toggle_type=api_data.get("toggle_type"),
            description=api_data.get("description"),
            support_url=api_data.get("support_url"),
            labels=api_data.get("labels"),
        )
