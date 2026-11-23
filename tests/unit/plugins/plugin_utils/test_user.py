"""Tests for Gateway user transformations."""

from ansible_collections.ansible.platform.plugins.plugin_utils.api.gateway.v1.user import UserTransformMixin_v1


def test_user_create_includes_associated_authenticators():
    operations = UserTransformMixin_v1.get_endpoint_operations()

    assert "associated_authenticators" in operations["create"].fields
