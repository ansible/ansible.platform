"""Unit tests for controller_meta action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock, mock_open, patch

import pytest
from ansible_collections.ansible.platform.plugins.action.controller_meta import ActionModule


@pytest.fixture
def action_module():
    """Create an ActionModule instance with mocked dependencies."""
    task = MagicMock()
    task.args = {}
    task.async_val = 0
    connection = MagicMock()
    play_context = MagicMock()
    loader = MagicMock()
    templar = MagicMock()
    shared_loader_obj = MagicMock()
    module = ActionModule(
        task=task,
        connection=connection,
        play_context=play_context,
        loader=loader,
        templar=templar,
        shared_loader_obj=shared_loader_obj,
    )
    return module


class TestControllerMeta:
    def test_run_returns_collection_metadata(self, action_module):
        galaxy_content = "---\nnamespace: ansible\nname: platform\nversion: 2.7.20260313\n"
        with patch("builtins.open", mock_open(read_data=galaxy_content)):
            result = action_module.run(task_vars={})

        assert result["changed"] is False
        assert result["namespace"] == "ansible"
        assert result["name"] == "platform"
        assert result["prefix"] == "ansible.platform"
        assert result["version"] == "2.7.20260313"

    def test_run_falls_back_to_manifest_json(self, action_module):
        manifest_content = '{"collection_info": {"version": "2.7.0"}}'

        def open_side_effect(path, *args, **kwargs):
            if "galaxy.yml" in str(path):
                raise OSError("not found")
            return mock_open(read_data=manifest_content)()

        with patch("builtins.open", side_effect=open_side_effect):
            result = action_module.run(task_vars={})

        assert result["changed"] is False
        assert result["prefix"] == "ansible.platform"
        assert result["version"] == "2.7.0"

    def test_run_returns_unknown_version_on_both_missing(self, action_module):
        with patch("builtins.open", side_effect=OSError("not found")):
            result = action_module.run(task_vars={})

        assert result["changed"] is False
        assert result["prefix"] == "ansible.platform"
        assert result["version"] == "unknown"

    def test_run_falls_back_on_empty_galaxy_yml(self, action_module):
        manifest_content = '{"collection_info": {"version": "2.7.0"}}'

        def open_side_effect(path, *args, **kwargs):
            if "galaxy.yml" in str(path):
                return mock_open(read_data="")()
            return mock_open(read_data=manifest_content)()

        with patch("builtins.open", side_effect=open_side_effect):
            result = action_module.run(task_vars={})

        assert result["version"] == "2.7.0"

    def test_get_collection_version_reads_galaxy_yml(self, action_module):
        galaxy_content = "---\nversion: 1.2.3\n"
        with patch("builtins.open", mock_open(read_data=galaxy_content)):
            version = action_module._get_collection_version()

        assert version == "1.2.3"

    def test_static_metadata_values(self, action_module):
        assert action_module._COLLECTION_NAMESPACE == "ansible"
        assert action_module._COLLECTION_NAME == "platform"
