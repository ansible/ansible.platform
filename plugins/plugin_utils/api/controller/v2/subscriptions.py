"""
API v2 Subscriptions dataclass and transform mixin.

Subscriptions uses a POST-to-query pattern: POST credentials to
/api/controller/v2/config/subscriptions/ to retrieve available subscriptions.
There is no standard CRUD lifecycle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APISubscriptions_v2(BaseTransformMixin):
    """API v2 representation of a subscription query."""

    subscriptions_username: Optional[str] = None
    subscriptions_password: Optional[str] = None
    subscriptions_client_id: Optional[str] = None
    subscriptions_client_secret: Optional[str] = None


class SubscriptionsTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for Subscriptions API v2.

    Subscriptions is a query-only resource: POST credentials to
    /config/subscriptions/ returns a list of available subscriptions.
    There is no list, create, update, or delete.
    """

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APISubscriptions_v2:
        username = getattr(ansible_instance, "username", None)
        password = getattr(ansible_instance, "password", None)
        client_id = getattr(ansible_instance, "client_id", None)
        client_secret = getattr(ansible_instance, "client_secret", None)

        if username and password:
            return APISubscriptions_v2(
                subscriptions_username=username,
                subscriptions_password=password,
            )
        return APISubscriptions_v2(
            subscriptions_client_id=client_id,
            subscriptions_client_secret=client_secret,
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "query": EndpointOperation(
                path="/api/controller/v2/config/subscriptions/",
                method="POST",
                fields=[
                    "subscriptions_username",
                    "subscriptions_password",
                    "subscriptions_client_id",
                    "subscriptions_client_secret",
                ],
                required_for="create",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return ""

    @classmethod
    def resolve(cls, ansible_instance, context: TransformContext) -> dict:
        """Query available subscriptions by POSTing credentials to the controller.

        This runs inside the manager subprocess, so direct session access is safe.
        """
        api_data = cls.from_ansible_data(ansible_instance, context)

        post_data = {}
        if api_data.subscriptions_username:
            post_data["subscriptions_username"] = api_data.subscriptions_username
            post_data["subscriptions_password"] = api_data.subscriptions_password
        else:
            post_data["subscriptions_client_id"] = api_data.subscriptions_client_id
            post_data["subscriptions_client_secret"] = api_data.subscriptions_client_secret

        url = context.manager._build_url(
            "/api/controller/v2/config/subscriptions/",
            service="controller",
            api_version=context.api_version,
        )
        logger.debug("POSTing to %s for subscription query", url)

        response = context.manager.session.post(
            url,
            json=post_data,
            timeout=context.manager.request_timeout,
            verify=context.manager.requests_verify,
        )
        response.raise_for_status()

        return {"subscriptions": response.json()}

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.subscriptions import AnsibleSubscriptions

        return AnsibleSubscriptions()
