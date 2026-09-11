# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for reusable BaseResourceActionPlugin preparation helpers."""

from __future__ import absolute_import, division, print_function

import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin


@dataclass
class Resource:
    name: str
    value: int = 0


class ExampleAction(BaseResourceActionPlugin):
    MODULE_NAME = "example"
    MODEL_CLASS = Resource
    _WRITE_ONLY_FIELDS = frozenset({"write_only"})
    _DEPRECATED_FIELDS = {"old_value": ("old_value is deprecated", "2.0.0")}


class TestActionPreparation(unittest.TestCase):
    def _make_action(self):
        action = ExampleAction.__new__(ExampleAction)
        action._task = MagicMock()
        action._task.args = {
            "name": "resource",
            "value": 3,
            "write_only": "secret",
            "old_value": "legacy",
        }
        action._display = MagicMock()
        return action

    def test_prepare_action_reuses_documentation_validation_and_manager(self):
        action = self._make_action()
        manager = MagicMock()
        validation = SimpleNamespace(
            validated_parameters=dict(action._task.args),
        )

        with patch.object(ActionBase, "run", return_value={"initial": True}) as base_run:
            with patch.object(action, "_get_documentation", return_value="module: example") as get_doc:
                with patch.object(action, "_build_argspec_from_docs", return_value={"argument_spec": {}}) as build_argspec:
                    with patch.object(action, "_validate_data", return_value=validation) as validate:
                        with patch.object(action, "_get_or_spawn_manager", return_value=(manager, {"platform": "fact"})) as get_manager:
                            prepared = action._prepare_action(task_vars={"inventory_hostname": "localhost"})

        base_run.assert_called_once()
        get_doc.assert_called_once_with()
        build_argspec.assert_called_once_with("module: example")
        validate.assert_called_once_with(action._task.args.copy(), {"argument_spec": {}}, "input")
        get_manager.assert_called_once_with({"inventory_hostname": "localhost"})
        self.assertIs(prepared["manager"], manager)
        self.assertEqual(prepared["resource_data"], {"name": "resource", "value": 3})
        self.assertEqual(prepared["write_only_data"], {"write_only": "secret"})
        self.assertEqual(prepared["result"]["ansible_facts"], {"platform": "fact"})
        self.assertEqual(prepared["result"]["deprecations"][0]["version"], "2.0.0")

    def test_build_resource_is_overridable(self):
        action = self._make_action()
        resource = action._build_resource({"name": "resource", "value": 4})
        self.assertEqual(resource, Resource(name="resource", value=4))

    def test_prepare_action_rejects_missing_documentation(self):
        action = self._make_action()

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value=""):
                with self.assertRaisesRegex(Exception, "Could not load DOCUMENTATION"):
                    action._prepare_action()


if __name__ == "__main__":
    unittest.main()
