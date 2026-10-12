"""Generate Ansible task YAML from MCP tool arguments.

Produces valid ansible.platform task YAML that can be pasted directly
into a playbook. Handles operation-to-state mapping and parameter formatting.
"""

from __future__ import annotations

from typing import Any

import yaml

# Operation -> Ansible state mapping
_OPERATION_TO_STATE: dict[str, str] = {
    "create": "present",
    "update": "present",
    "delete": "absent",
    "find": "exists",
}

# Operation -> human-readable verb for task name
_OPERATION_VERBS: dict[str, str] = {
    "create": "Create",
    "update": "Update",
    "delete": "Delete",
    "find": "Check",
}


def emit_task(module_name: str, operation: str, params: dict[str, Any]) -> str:
    """Generate Ansible task YAML for a given module operation.

    Args:
        module_name: Resource module name (e.g. 'user').
        operation: Operation name ('create', 'update', 'delete', 'find').
        params: Resource parameters (mode/operation already stripped).

    Returns:
        YAML string representing an Ansible task list.
    """
    state = _OPERATION_TO_STATE.get(operation, "present")
    verb = _OPERATION_VERBS.get(operation, operation.title())

    # Build a readable task name from the resource and a lookup field
    lookup_value = _guess_resource_label(params, module_name)
    if lookup_value:
        task_name = f"{verb} {module_name} {lookup_value}"
    else:
        task_name = f"{verb} {module_name}"

    # Build module arguments
    module_args: dict[str, Any] = {}
    module_args.update(params)
    module_args["state"] = state

    # Remove None values to keep YAML clean
    module_args = {k: v for k, v in module_args.items() if v is not None}

    task = {
        "name": task_name,
        f"ansible.platform.{module_name}": module_args,
    }

    return yaml.dump([task], default_flow_style=False, sort_keys=False, allow_unicode=True)


def _guess_resource_label(params: dict[str, Any], module_name: str) -> str | None:
    """Extract a human-readable label from params for the task name.

    Checks common lookup fields in priority order.
    """
    for field in ("name", "username", "slug", "id"):
        val = params.get(field)
        if val is not None:
            return str(val)
    return None
