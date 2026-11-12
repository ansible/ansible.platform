"""Prepare Batch 3 AWX scenarios without making API calls or changing source tests."""

import argparse
import importlib.util
import json
import shutil
from pathlib import Path

import yaml

TARGETS = {
    "team": "team",
    "workflow_launch": "workflow_launch",
    "export": "export",
    # AWX devel embeds the node scenarios in its workflow template target.
    "workflow_job_template_node": "workflow_job_template",
    "label": "label",
    "job_list": "job_list",
    "instance_group": "instance_group",
}


def main():
    """Copy scenarios and use the compatibility skill to rewrite subject actions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", type=Path, required=True)
    parser.add_argument("--awx-repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("compat_adapter", args.skill_dir / "scripts/prepare_platform_integration_targets.py")
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    manifest = []
    auth = {key: "{{ " + key + " }}" for key in ("gateway_hostname", "gateway_username", "gateway_password")}
    auth["gateway_validate_certs"] = "{{ gateway_validate_certs | bool }}"
    for module, source_target in TARGETS.items():
        source = args.awx_repo / "awx_collection/tests/integration/targets" / source_target
        destination = args.output_dir / "targets" / module
        shutil.copytree(source, destination)
        rewritten = set()
        for file in sorted((destination / "tasks").rglob("*.yml")):
            tasks = yaml.safe_load(file.read_text())
            rewritten.update(adapter.rewrite_tasks(tasks, {module: module}))
            file.write_text(yaml.safe_dump(tasks, sort_keys=False))
        if module not in rewritten:
            raise ValueError("No subject calls found for " + module)
        play = [
            {
                "hosts": "localhost",
                "connection": "local",
                "gather_facts": False,
                "collections": ["awx.awx"],
                "module_defaults": {"ansible.platform." + module: auth},
                "tasks": [{"ansible.builtin.include_tasks": str((destination / "tasks/main.yml").resolve())}],
            }
        ]
        (args.output_dir / (module + ".yml")).write_text(yaml.safe_dump(play, sort_keys=False))
        manifest.append({"module": module, "legacy_target": source_target, "assertions_modified": False})
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Prepared seven scenarios; legacy inputs and assertions are preserved. No API calls made.")


if __name__ == "__main__":
    main()
