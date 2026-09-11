#!/usr/bin/env bash
# Enforce SDK execution invariants in action plugins.
# See docs/09-agent-collaboration.md §10 and docs/05-design-principles.md §3a.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION_DIR="${ROOT}/plugins/action"

if [[ ! -d "${ACTION_DIR}" || -L "${ACTION_DIR}" ]]; then
    echo "ERROR: Action plugin directory not found: ${ACTION_DIR}" >&2
    exit 1
fi

python3 - "${ROOT}" "${ACTION_DIR}" <<'PY'
import ast
import os
import re
import sys

root, action_dir = sys.argv[1:]
violations = []
url_pattern = re.compile(r"(?:https?://|/api/)")


def location(path, node, message):
    violations.append(f"{os.path.relpath(path, root)}:{node.lineno}: {message}")


def call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def is_session_expression(node):
    return isinstance(node, ast.Name) and node.id == "session" or (
        isinstance(node, ast.Attribute) and node.attr == "session"
    )


def has_find_execute(node):
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or call_name(child.func) != "execute":
            continue
        for keyword in child.keywords:
            if keyword.arg == "operation" and isinstance(keyword.value, ast.Constant) and keyword.value.value == "find":
                return True
    return False


def docstring_values(tree):
    values = set()
    for parent in ast.walk(tree):
        if isinstance(parent, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and parent.body:
            first = parent.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                values.add(id(first.value))
    return values


for directory, dirnames, filenames in os.walk(action_dir, followlinks=False):
    dirnames[:] = [name for name in dirnames if not os.path.islink(os.path.join(directory, name))]
    for filename in filenames:
        path = os.path.join(directory, filename)
        if not filename.endswith(".py") or os.path.islink(path) or not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as source:
                tree = ast.parse(source.read(), filename=path)
        except (OSError, SyntaxError) as exc:
            print(f"ERROR: Could not scan {path}: {exc}", file=sys.stderr)
            sys.exit(2)

        documentation = docstring_values(tree)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names]
                if any(name == "requests" or name.startswith("requests.") for name in names):
                    location(path, node, "direct requests import")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and url_pattern.search(node.value):
                if id(node) in documentation:
                    continue
                location(path, node, "hardcoded API URL")
            elif isinstance(node, ast.Attribute) and node.attr == "session":
                location(path, node, "direct session access")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"get", "post", "put", "patch", "delete"} and is_session_expression(node.func.value):
                    location(path, node, "direct session HTTP call")
            elif isinstance(node, ast.While) and has_find_execute(node):
                location(path, node, "polling loop performs manager.execute(operation='find')")

if violations:
    print("ERROR: Action plugins violate SDK execution invariants:", file=sys.stderr)
    print("Use PlatformService.execute() and transform mixins instead.", file=sys.stderr)
    print("See docs/09-agent-collaboration.md section 10.", file=sys.stderr)
    print("\n".join(violations), file=sys.stderr)
    sys.exit(1)
PY

echo "check_action_plugin_invariants: OK"
