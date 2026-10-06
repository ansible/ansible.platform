"""
Check GitHub workflows for secret exposure vulnerabilities.

This script scans .github/workflows/ for dangerous patterns:
- Workflows that use secrets AND trigger on pull_request without proper gates
- pull_request_target workflows that check out PR code with secrets
- Missing authorization checks (label gates, member checks)

Usage:
    python3 check_workflow_secrets.py

Exit codes:
    0 - No issues found
    1 - Security issues detected
"""

import sys
from pathlib import Path
import yaml


def check_workflow_secret_exposure():
    """Check all workflows for secret exposure vulnerabilities."""

    workflows_dir = Path(".github/workflows")
    if not workflows_dir.exists():
        print("⚠️  No .github/workflows/ directory found")
        return 0

    issues_found = False

    # Scan both .yml and .yaml extensions
    workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))

    if not workflow_files:
        print("⚠️  No workflow files found in .github/workflows/")
        return 0

    for wf_file in workflow_files:
        with open(wf_file) as f:
            wf = yaml.safe_load(f)
            content = wf_file.read_text()

        # PyYAML converts unquoted 'on' to boolean True in YAML 1.1
        # Check both 'on' and True keys
        triggers = wf.get("on") or wf.get(True) or {}
        has_pr = False
        has_pr_target = False

        # Handle all trigger forms: scalar, list, and mapping
        if isinstance(triggers, str):
            # Scalar: on: pull_request
            has_pr = triggers == "pull_request"
            has_pr_target = triggers == "pull_request_target"
        elif isinstance(triggers, list):
            # List: on: [pull_request, push]
            has_pr = "pull_request" in triggers
            has_pr_target = "pull_request_target" in triggers
        elif isinstance(triggers, dict):
            # Mapping: on:\n  pull_request:\n    types: [labeled]
            has_pr = "pull_request" in triggers
            has_pr_target = "pull_request_target" in triggers

        # Check for secret usage
        has_secrets = "secrets." in content

        # Check authorization gates in actual job conditions (not comments)
        has_label_gate = False
        has_member_check = False

        for job_name, job in wf.get("jobs", {}).items():
            job_if = job.get("if", "")
            if "github.event.label.name == 'safe to test'" in job_if:
                has_label_gate = True
            if "author_association" in job_if or "MEMBER" in job_if:
                has_member_check = True

        # Check 1: pull_request + secrets without proper gate
        if has_pr and has_secrets and not (has_label_gate or has_member_check):
            print(f"❌ DANGER: {wf_file.name} exposes secrets to fork PRs without proper gate!")
            print("   → Add label gate: if: github.event.label.name == 'safe to test'")
            print(f"   → Or member check: if: github.event.pull_request.author_association == 'MEMBER'")
            issues_found = True

        # Check 2: pull_request_target with PR code checkout
        if has_pr_target:
            for job_name, job in wf.get("jobs", {}).items():
                for step in job.get("steps", []):
                    checkout_ref = step.get("with", {}).get("ref", "")
                    if "head.sha" in checkout_ref or "head_sha" in checkout_ref or "head.ref" in checkout_ref:
                        print(f"⚠️  WARNING: {wf_file.name} checks out PR code with pull_request_target")
                        print(f"   Job: {job_name}")
                        print("   → This allows PR code to access GITHUB_TOKEN with write permissions")
                        issues_found = True

    if not issues_found:
        print("✅ No secret exposure issues found in workflows")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(check_workflow_secret_exposure())
