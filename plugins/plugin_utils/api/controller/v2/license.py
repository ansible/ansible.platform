"""
Controller license API dataclass and transform mixin.

License uses a singleton config endpoint (/config/) for find and delete.
Create has two variants: manifest POST to /config/, subscription POST to /config/attach/.
The mixin declares is_singleton=True so the framework handles find correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

CONFIG_ENDPOINT = "config/"
ATTACH_ENDPOINT = "config/attach/"


@dataclass
class APILicense_v2(BaseTransformMixin):
    """API v2 representation of a Controller license."""

    manifest: Optional[str] = None
    subscription_id: Optional[str] = None


class LicenseTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for Controller license API v2.

    License is a singleton: GET /config/ returns the full config including
    license_info.  POST /config/ attaches a manifest, POST /config/attach/
    attaches via subscription ID, DELETE /config/ removes the license.
    """

    is_singleton = True

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APILicense_v2:
        return APILicense_v2(
            manifest=getattr(ansible_instance, "manifest", None),
            subscription_id=getattr(ansible_instance, "subscription_id", None),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "get": EndpointOperation(
                path=CONFIG_ENDPOINT,
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
            "create": EndpointOperation(
                path=CONFIG_ENDPOINT,
                method="POST",
                fields=["manifest"],
                required_for="create",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return ""

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.license import AnsibleLicense

        return AnsibleLicense(
            license_info=api_data.get("license_info", {}),
        )
