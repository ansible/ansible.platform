"""Prepare isolated Batch 2 legacy scenarios; never execute or authenticate them."""

import argparse
import importlib.util
import json
import shutil
from pathlib import Path

import yaml

MODULES = {
    "organization": "organization",
    "workflow_job_template": "workflow_job_template",
    "execution_environment": "execution_environment",
    "group": "group",
    "token": "token",
    "job_wait": "job_wait",
    "settings": "controller_settings",
    "notification_template": "notification_template",
    "project_update": "project_update",
}


def adapt(tasks, fqcn, module, states, omitted):
    """Apply only the explicitly recorded diagnostic adaptations."""
    for task in tasks:
        if not isinstance(task, dict):
            continue
        action = task.get(fqcn)
        if isinstance(action, dict):
            name = str(action.get("name"))
            if action.get("state") == "exists" and states.get(name) == "absent":
                action["state"] = "present"
            states[name] = action.get("state", "present")
            if "controller_oauthtoken" in action:
                action["aap_token"] = action.pop("controller_oauthtoken")
        assertion = task.get("assert", task.get("ansible.builtin.assert", {}))
        conditions = assertion.get("that", [])
        if isinstance(conditions, list):
            removed = [c for c in conditions if ".msg" in str(c) or (module == "group" and "result.total_results" in str(c))]
            if removed:
                omitted.append({"task": task.get("name", "assert"), "conditions": removed})
                assertion["that"] = [c for c in conditions if c not in removed]
        for key in ("block", "rescue", "always"):
            if isinstance(task.get(key), list):
                adapt(task[key], fqcn, module, states, omitted)


def main():
    """Copy source scenarios and use the updated skill to qualify subject calls."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", type=Path, required=True)
    parser.add_argument("--awx-repo", type=Path, required=True)
    parser.add_argument("--token-repo", type=Path, required=True, help="Stable Controller checkout containing awx_collection")
    parser.add_argument("--output-dir", type=Path, required=True, help="A new directory; source scenarios are never overwritten")
    parser.add_argument("--adapt-known-differences", action="store_true", help="Diagnostic continuation, not a legacy parity run")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("compat_adapter", args.skill_dir / "scripts/prepare_platform_integration_targets.py")
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    omitted = {}
    for legacy, platform in MODULES.items():
        source_root = args.token_repo if legacy == "token" else args.awx_repo
        source = source_root / "awx_collection/tests/integration/targets" / legacy
        target = args.output_dir / "targets" / legacy
        shutil.copytree(source, target)
        fqcn = "ansible.platform." + platform
        omitted[legacy] = []
        for file in sorted((target / "tasks").rglob("*.yml")):
            content = file.read_text()
            if args.adapt_known_differences and legacy == "token":
                content = content.replace("controller_token", "aap_token")
            tasks = yaml.safe_load(content)
            adapter.rewrite_tasks(tasks, {legacy: platform})
            if args.adapt_known_differences:
                adapt(tasks, fqcn, legacy, {}, omitted[legacy])
            file.write_text(yaml.safe_dump(tasks, sort_keys=False))
        auth = {k: "{{ " + k + " }}" for k in ("gateway_hostname", "gateway_username", "gateway_password")}
        play = [
            {
                "hosts": "localhost",
                "connection": "local",
                "gather_facts": False,
                "collections": ["awx.awx"],
                "module_defaults": {fqcn: auth},
                "tasks": [{"ansible.builtin.include_tasks": str((target / "tasks/main.yml").resolve())}],
            }
        ]
        (args.output_dir / (legacy + ".yml")).write_text(yaml.safe_dump(play, sort_keys=False))
    (args.output_dir / "omitted-diagnostic-assertions.json").write_text(json.dumps(omitted, indent=2) + "\n")
    print("Prepared nine scenarios. No API calls made. Review omitted-diagnostic-assertions.json before interpreting adapted results.")


if __name__ == "__main__":
    main()
