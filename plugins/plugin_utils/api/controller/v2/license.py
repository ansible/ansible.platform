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
from ....platform.types import EndpointOperation, SingletonMutationPlan, TransformContext

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
            "attach": EndpointOperation(
                path=ATTACH_ENDPOINT,
                method="POST",
                fields=["subscription_id"],
                required_for="attach",
                order=1,
            ),
            "delete": EndpointOperation(
                path=CONFIG_ENDPOINT,
                method="DELETE",
                fields=[],
                required_for="delete",
                order=1,
            ),
        }

    @classmethod
    def validate_mutation(cls, ansible_data, context):
        """Reject unsupported operations and ambiguous or missing license sources."""
        if context.operation not in {"create", "delete"}:
            raise ValueError("License supports find, create, and delete operations")
        if not isinstance(ansible_data.force, bool):
            raise ValueError("force must be a boolean")
        if context.operation == "create":
            manifest = ansible_data.manifest
            subscription_id = ansible_data.subscription_id
            if bool(manifest) == bool(subscription_id):
                raise ValueError("Exactly one non-empty manifest or subscription_id is required")
            for name, value in (("manifest", manifest), ("subscription_id", subscription_id)):
                if value is not None and not isinstance(value, str):
                    raise ValueError("%s must be a string" % name)

    @classmethod
    def plan_mutation(cls, ansible_data, current, context):
        """Choose license endpoint steps using the same rules for every consumer."""
        license_info = current.get("license_info") or {}
        if context.operation == "delete":
            if not (license_info.get("license_type") or license_info.get("instance_count")):
                return SingletonMutationPlan([], {"changed": False, "msg": "No license to remove"})
            result = {"changed": True}
            if not context.check_mode:
                result["msg"] = "License removed"
            return SingletonMutationPlan(["delete"], result)

        already_licensed = license_info.get("instance_count", 0) > 0 and license_info.get("valid_key", False) and not license_info.get("trial", True)
        if already_licensed and not ansible_data.force:
            return SingletonMutationPlan(
                [],
                {"changed": False, "license_info": license_info, "msg": "Already licensed. Use force=true to re-apply."},
            )
        steps = ["create"] if ansible_data.manifest else ["attach", "get"]
        return SingletonMutationPlan(steps, {"changed": True})

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
