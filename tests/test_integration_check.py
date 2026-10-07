#!/usr/bin/env python

import os
from sys import exit

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
# CI provisions Gateway only. Run Controller live tests when CI has a routed Controller service.
modules_without_live_integration = {
    "job_templates": "Controller requires a routed service; job_template_mock runs in Molecule CI",
}
tests_to_ignore = ["lookup_test", "setup_gateway", "users_examples_test", "backward_compat_26_test", "ssl_env_forwarding_test", "vault_credentials_test"]


def get_files(dir_name):
    return [f for f in os.listdir(dir_name) if os.path.isfile(os.path.join(dir_name, f))]


def get_dirs(dir_name):
    return [f for f in os.listdir(dir_name) if os.path.isdir(os.path.join(dir_name, f))]


plugins = get_files(os.path.join(base_dir, "plugins", "modules"))
tests = get_dirs(os.path.join(base_dir, "tests", "integration", "targets"))
for test_name in tests_to_ignore:
    tests.remove(test_name)

missing_tests = []
for plugin in plugins:
    plugin = plugin.replace(".py", "")
    if plugin[-1] != "s":
        plugin = f"{plugin}s"
    # If we every have something like inventory we will need to update this for `ies``.

    test_name = f"{plugin}_test"
    if test_name not in tests:
        missing_tests.append(plugin)
    else:
        tests.remove(test_name)

exit_code = 0
if missing_tests:
    print("Missing a test for the following plugins:")
    for test_name in missing_tests:
        if test_name in modules_without_live_integration:
            print(f"    {test_name} [OK, {modules_without_live_integration[test_name]}]")
        else:
            print(f"    {test_name}")
            exit_code = 1

if tests:
    print("We have tests for no plugins:")
    for test_name in tests:
        print(f"    {test_name}")
    exit_code = 1

exit(exit_code)
