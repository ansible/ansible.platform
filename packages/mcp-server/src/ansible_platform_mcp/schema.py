"""Convert Ansible module argspec options to JSON Schema inputSchema.

Maps Ansible DOCUMENTATION option types to JSON Schema types and handles
choices, defaults, required fields, list elements, suboptions, and aliases.
"""

from __future__ import annotations

from typing import Any

# Ansible type string -> JSON Schema type
_TYPE_MAP: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "path": "string",
    "raw": "string",
}


def _option_to_json_schema(option_spec: dict[str, Any]) -> dict[str, Any]:
    """Convert a single Ansible option spec to a JSON Schema property.

    Args:
        option_spec: Ansible option dict (type, description, choices, default, etc.)

    Returns:
        JSON Schema property definition.
    """
    ansible_type = option_spec.get("type", "str")
    schema: dict[str, Any] = {}

    # Handle 'raw' as oneOf string or object
    if ansible_type == "raw":
        schema["oneOf"] = [{"type": "string"}, {"type": "object"}]
    else:
        json_type = _TYPE_MAP.get(ansible_type, "string")
        schema["type"] = json_type

    # Description
    raw_desc = option_spec.get("description", [])
    if isinstance(raw_desc, list):
        desc = " ".join(str(d) for d in raw_desc)
    else:
        desc = str(raw_desc)

    # Append aliases to description
    aliases = option_spec.get("aliases", [])
    if aliases:
        desc += f" (aliases: {', '.join(aliases)})"

    if desc:
        schema["description"] = desc

    # Choices -> enum
    choices = option_spec.get("choices")
    if choices:
        schema["enum"] = list(choices)

    # Default value
    if "default" in option_spec:
        schema["default"] = option_spec["default"]

    # List items
    if ansible_type == "list":
        elements = option_spec.get("elements", "str")
        if elements == "dict":
            suboptions = option_spec.get("suboptions", {})
            if suboptions:
                schema["items"] = _options_to_json_schema(suboptions)
            else:
                schema["items"] = {"type": "object"}
        else:
            schema["items"] = {"type": _TYPE_MAP.get(elements, "string")}

    # Dict suboptions (nested object)
    if ansible_type == "dict":
        suboptions = option_spec.get("suboptions", {})
        if suboptions:
            nested = _options_to_json_schema(suboptions)
            schema["properties"] = nested.get("properties", {})
            if nested.get("required"):
                schema["required"] = nested["required"]

    return schema


def _options_to_json_schema(options: dict[str, Any]) -> dict[str, Any]:
    """Convert an Ansible options dict to a JSON Schema object.

    Args:
        options: Dict of option_name -> option_spec.

    Returns:
        JSON Schema object with properties and required list.
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, spec in options.items():
        if not isinstance(spec, dict):
            continue
        properties[name] = _option_to_json_schema(spec)
        if spec.get("required"):
            required.append(name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


def build_tool_schema(
    module_name: str,
    options: dict[str, Any],
    has_state: bool,
) -> dict[str, Any]:
    """Build a complete MCP tool inputSchema for a module.

    Adds synthetic 'operation' and 'mode' parameters alongside
    the module's own resource options.

    Args:
        module_name: Module name (e.g. 'user').
        options: Module options dict (auth options already stripped).
        has_state: Whether the module has a state option.

    Returns:
        Complete JSON Schema suitable for MCP Tool.inputSchema.
    """
    base_schema = _options_to_json_schema(options)
    properties = base_schema.get("properties", {})
    required = list(base_schema.get("required", []))

    # Remove 'state' from properties -- operation replaces it
    properties.pop("state", None)
    if "state" in required:
        required.remove("state")

    # Add operation parameter
    if has_state:
        operations = ["create", "update", "delete", "find"]
    else:
        operations = ["update"]

    properties["operation"] = {
        "type": "string",
        "enum": operations,
        "description": (
            "Operation to perform. "
            "'create' ensures the resource exists (idempotent). "
            "'update' modifies an existing resource. "
            "'delete' removes the resource. "
            "'find' returns the current state without changes."
        ),
    }

    # Add mode parameter
    properties["mode"] = {
        "type": "string",
        "enum": ["execute", "emit"],
        "default": "execute",
        "description": (
            "Execution mode. "
            "'execute' calls the AAP Gateway API directly and returns the result. "
            "'emit' returns the equivalent ansible.platform task YAML for use in a playbook."
        ),
    }

    # operation is required, mode is not (defaults to execute)
    if "operation" not in required:
        required.append("operation")

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }
