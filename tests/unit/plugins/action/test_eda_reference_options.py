# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from types import SimpleNamespace

import pytest
import yaml
from ansible.utils.display import Display
from ansible_collections.ansible.platform.plugins.action import (
    decision_environment,
    eda_credential_input_source,
    eda_project,
    event_stream,
    rulebook_activation,
)


@pytest.mark.parametrize(
    ("module", "name"),
    [
        (decision_environment, "organization"),
        (eda_credential_input_source, "organization"),
        (eda_project, "organization"),
        (event_stream, "organization"),
        (rulebook_activation, "organization"),
        (rulebook_activation, "rulebook"),
        (rulebook_activation, "decision_environment"),
        (rulebook_activation, "awx_token"),
    ],
)
def test_short_reference_names_preserve_runtime_fields(module, name):
    legacy_name = f"{name}_name"
    action = module.ActionModule.__new__(module.ActionModule)
    action._display = Display()
    documented_options = yaml.safe_load(action._get_documentation())["options"]
    assert legacy_name in documented_options[name]["aliases"]

    required_args = {"name": "example"}
    if module is decision_environment:
        required_args["image_url"] = "example.invalid/decision-environment"
    elif module is eda_credential_input_source:
        required_args = {"input_field_name": "password", "source_credential": "source", "target_credential": "target"}

    for args, expected in (
        ({legacy_name: "Existing resource"}, "Existing resource"),
        ({name: 42}, "42"),
        ({legacy_name: "Conflicting resource", name: "New input"}, "New input"),
    ):
        action._task = SimpleNamespace(args={**required_args, **args})
        validated = action._validate_action_input()
        assert validated.validated_params[legacy_name] == expected


def test_rulebook_activation_token_alias_keeps_precedence():
    action = rulebook_activation.ActionModule.__new__(rulebook_activation.ActionModule)
    action._display = Display()
    action._task = SimpleNamespace(args={"name": "example", "awx_token": "short", "awx_token_name": "long", "token": "existing alias"})

    assert action._validate_action_input().validated_params["awx_token_name"] == "existing alias"


def test_eda_project_supports_scm_credential_alias():
    action = eda_project.ActionModule.__new__(eda_project.ActionModule)
    action._display = Display()
    documented_options = yaml.safe_load(action._get_documentation())["options"]

    assert "scm_credential" in documented_options["credential"]["aliases"]

    for args, expected in (
        ({"scm_credential": "Existing credential"}, "Existing credential"),
        ({"credential": "New credential"}, "New credential"),
    ):
        action._task = SimpleNamespace(args={"name": "example", **args})
        validated = action._validate_action_input()
        assert validated.validated_params["credential"] == expected
