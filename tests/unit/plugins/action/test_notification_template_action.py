"""Unit tests for notification-template idempotency behavior."""

from ansible_collections.ansible.platform.plugins.action.notification_template import ActionModule


def _make_action():
    return ActionModule.__new__(ActionModule)


def test_notification_configuration_tolerates_api_defaults_and_encrypted_values():
    action = _make_action()

    assert not action._should_update(
        {
            "name": "Webhook",
            "notification_configuration": {
                "url": "https://example.invalid/webhook",
                "headers": {"Authorization": "secret"},
            },
        },
        {
            "name": "Webhook",
            "notification_configuration": {
                "url": "https://example.invalid/webhook",
                "http_method": "POST",
                "headers": {"Authorization": "$encrypted$"},
            },
        },
    )


def test_notification_configuration_detects_requested_value_changes():
    action = _make_action()

    assert action._should_update(
        {"name": "Webhook", "notification_configuration": {"url": "https://example.invalid/updated"}},
        {"name": "Webhook", "notification_configuration": {"url": "https://example.invalid/webhook"}},
    )
