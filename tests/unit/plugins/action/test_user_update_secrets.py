"""Tests for user password update intent passed to the client."""

from __future__ import absolute_import, division, print_function

import uuid
from importlib import import_module
from unittest.mock import Mock

import pytest

ActionModule = import_module("ansible_collections.ansible.platform.plugins.action.user").ActionModule


@pytest.mark.parametrize(("update_secrets", "force_update"), [(True, True), (False, False)])
def test_password_update_passes_force_flag_only_when_secret_updates_are_enabled(update_secrets, force_update):
    action = ActionModule.__new__(ActionModule)
    action._task = Mock(args={"update_secrets": update_secrets})
    ansible_data = {}
    test_password = uuid.uuid4().hex

    action._pre_execute_hook(
        ansible_data,
        {"password": test_password},
        {"update_secrets": update_secrets},
        "update",
    )

    assert ansible_data["password"] == test_password
    assert ansible_data.get("_platform_force_update", False) is force_update


def test_password_create_does_not_force_an_update():
    action = ActionModule.__new__(ActionModule)
    action._task = Mock(args={"update_secrets": True})
    ansible_data = {}
    test_password = uuid.uuid4().hex

    action._pre_execute_hook(ansible_data, {"password": test_password}, {"update_secrets": True}, "create")

    assert ansible_data == {"password": test_password}
