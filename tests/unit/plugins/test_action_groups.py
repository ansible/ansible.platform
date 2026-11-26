# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for collection action groups consumed by module_defaults."""

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


def test_aap_action_group_resolves_all_service_modules(tmp_path):
    collection_root = Path(__file__).resolve().parents[3]
    collection = tmp_path / "ansible_collections" / "ansible" / "platform"
    collection.parent.mkdir(parents=True)
    collection.symlink_to(collection_root, target_is_directory=True)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json
from ansible.playbook.play import Play
from ansible.plugins.loader import init_plugin_loader

init_plugin_loader()
play = Play.load({
    "hosts": "localhost",
    "module_defaults": {"group/ansible.platform.aap": {"aap_hostname": "gateway.example"}},
})
print(json.dumps({name: sorted(set(modules)) for name, modules in play._group_actions.items()}))
""",
        ],
        env={**os.environ, "ANSIBLE_COLLECTIONS_PATH": str(tmp_path), "ANSIBLE_HOME": str(tmp_path)},
        check=True,
        capture_output=True,
        text=True,
    )

    groups = yaml.safe_load((collection_root / "meta/runtime.yml").read_text())["action_groups"]
    service_groups = {
        f"ansible.platform.{service}": sorted(f"ansible.platform.{module}" for module in groups[service]) for service in ("gateway", "controller", "eda")
    }
    assert json.loads(result.stdout) == {
        **service_groups,
        "ansible.platform.aap": sorted({module for modules in service_groups.values() for module in modules}),
    }
