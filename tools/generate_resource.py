"""
Generate boilerplate files for a new platform collection resource module from the
Gateway OpenAPI specification.

Usage (from the collection root):
    python tools/generate_resource.py \\
        --tag services \\
        --spec /path/to/gateway.json \\
        [--dry-run]

For each resource tag the generator creates (unless the file already exists):
    plugins/plugin_utils/api/v1/{resource}.py          – TransformMixin + API dataclass
    plugins/plugin_utils/ansible_models/{resource}.py  – AnsibleModel dataclass with resource metadata
    plugins/modules/{resource}.py                      – Module with DOCUMENTATION (config list + RM states)
    plugins/action/{resource}.py                       – Action plugin (minimal: USER_MODEL only)
    tests/integration/targets/{resource}_test/tasks/main.yml  – Integration test scaffold

Use --dry-run to preview what would be generated without writing files.
Use --overwrite to replace existing files (default: skip existing).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from textwrap import indent
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Spec helpers
# ---------------------------------------------------------------------------

_SCALAR_TYPE_MAP = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "object": "Dict[str, Any]",
    "array": "List[Any]",
}

_READ_ONLY_NAMES = {"id", "url", "created", "modified", "created_by", "modified_by", "related", "summary_fields"}


def resolve_ref(spec: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Follow a $ref to components/schemas."""
    ref = schema.get("$ref", "")
    if ref.startswith("#/components/schemas/"):
        name = ref.split("/")[-1]
        return spec.get("components", {}).get("schemas", {}).get(name, {})
    return schema


def collect_properties_with_meta(
    spec: Dict[str, Any],
    schema: Dict[str, Any],
    depth: int = 0,
) -> Dict[str, Dict[str, Any]]:
    """
    Return {field_name: {type, readOnly, nullable, required, description}} for
    all properties in a schema, handling $ref, allOf, anyOf, oneOf.
    """
    if depth > 8:
        return {}
    if "$ref" in schema:
        schema = resolve_ref(spec, schema)
    result: Dict[str, Dict[str, Any]] = {}
    for name, prop in schema.get("properties", {}).items():
        resolved = prop if "$ref" not in prop else resolve_ref(spec, prop)
        py_type = _SCALAR_TYPE_MAP.get(resolved.get("type", ""), "Any")
        result[name] = {
            "type": py_type,
            "readOnly": resolved.get("readOnly", name in _READ_ONLY_NAMES),
            "nullable": resolved.get("nullable", False),
            "description": resolved.get("description", ""),
            "required": False,  # filled in separately from schema["required"]
        }
    for req_field in schema.get("required", []):
        if req_field in result:
            result[req_field]["required"] = True
    for combiner in ("allOf", "anyOf", "oneOf"):
        for sub in schema.get(combiner, []):
            sub_props = collect_properties_with_meta(spec, sub, depth + 1)
            for k, v in sub_props.items():
                if k not in result:
                    result[k] = v
    return result


def get_schema_for_operation(spec: Dict[str, Any], path: str, method: str) -> Dict[str, Any]:
    """Return the resolved schema for the request body of (path, method)."""
    op = spec.get("paths", {}).get(path, {}).get(method.lower(), {})
    content = op.get("requestBody", {}).get("content", {})
    schema = content.get("application/json", {}).get("schema", {}) or content.get("application/x-www-form-urlencoded", {}).get("schema", {})
    if "$ref" in schema:
        schema = resolve_ref(spec, schema)
    return schema


def get_paths_for_tag(spec: Dict[str, Any], tag: str) -> List[Tuple[str, str, str]]:
    """Return [(path, method, operationId)] for all operations with the given tag."""
    result = []
    for path, path_item in spec.get("paths", {}).items():
        for method, op in path_item.items():
            if not isinstance(op, dict):
                continue
            if tag in op.get("tags", []):
                result.append((path, method.upper(), op.get("operationId", "")))
    return result


# ---------------------------------------------------------------------------
# Resource model
# ---------------------------------------------------------------------------


class ResourceSpec:
    """Encapsulates the spec-derived information for one resource type."""

    def __init__(self, tag: str, spec: Dict[str, Any]):
        self.tag = tag
        self.spec = spec

        # snake_case resource name (e.g. "service_cluster")
        self.name = tag.rstrip("s").replace("-", "_")  # crude singularization
        # Proper Python class prefix (e.g. "ServiceCluster")
        self.class_prefix = "".join(w.capitalize() for w in self.name.split("_"))

        # Derive paths
        all_ops = get_paths_for_tag(spec, tag)
        self.list_path: Optional[str] = None
        self.detail_path: Optional[str] = None
        self.methods: Dict[str, Set[str]] = {}  # path -> set of methods
        for path, method, _op_info in all_ops:
            self.methods.setdefault(path, set()).add(method)
            if path.endswith("}/") and "{" in path:
                if self.detail_path is None:
                    self.detail_path = path
            else:
                if self.list_path is None and path.count("/") >= 4:
                    self.list_path = path

        # Derive properties from POST (create) schema or GET (list) schema
        create_schema: Dict[str, Any] = {}
        if self.list_path and "POST" in self.methods.get(self.list_path, set()):
            create_schema = get_schema_for_operation(spec, self.list_path, "POST")
        elif self.detail_path and "PATCH" in self.methods.get(self.detail_path, set()):
            create_schema = get_schema_for_operation(spec, self.detail_path, "PATCH")

        self.properties = collect_properties_with_meta(spec, create_schema)

        # Partition fields
        self.read_only_fields: List[str] = []
        self.writable_fields: List[str] = []
        self.required_fields: List[str] = []
        for name, meta in self.properties.items():
            if meta["readOnly"] or name in _READ_ONLY_NAMES:
                self.read_only_fields.append(name)
            else:
                self.writable_fields.append(name)
                if meta["required"]:
                    self.required_fields.append(name)

        # Available CRUD operations
        self.has_create = self.list_path is not None and "POST" in self.methods.get(self.list_path, set())
        self.has_update = self.detail_path is not None and "PATCH" in self.methods.get(self.detail_path, set())
        self.has_delete = self.detail_path is not None and "DELETE" in self.methods.get(self.detail_path, set())
        self.has_list = self.list_path is not None and "GET" in self.methods.get(self.list_path, set())
        self.has_get = self.detail_path is not None and "GET" in self.methods.get(self.detail_path, set())

        # Lookup field (first required writable string field, fallback "name")
        self.lookup_field = "name"
        for fname in self.required_fields:
            meta = self.properties.get(fname, {})
            if meta.get("type") == "str":
                self.lookup_field = fname
                break

    def summary(self) -> str:
        lines = [
            f"Resource: {self.name} (tag={self.tag})",
            f"  list_path   : {self.list_path}",
            f"  detail_path : {self.detail_path}",
            f"  CRUD        : create={self.has_create} update={self.has_update} delete={self.has_delete} list={self.has_list}",
            f"  required    : {self.required_fields}",
            f"  writable    : {self.writable_fields}",
            f"  read-only   : {self.read_only_fields}",
            f"  lookup_field: {self.lookup_field}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Code generators — Resource Module pattern
# ---------------------------------------------------------------------------


def _py_type_hint(meta: Dict[str, Any]) -> str:
    base = meta.get("type", "Any")
    if meta.get("nullable") or not meta.get("required"):
        return f"Optional[{base}]"
    return base


def _ansible_type(py_type: str) -> str:
    """Map Python type hint to Ansible DOCUMENTATION type string."""
    return {"int": "int", "bool": "bool", "float": "float"}.get(py_type, "str")


def gen_api_v1(res: ResourceSpec) -> str:
    """Generate plugins/plugin_utils/api/v1/{resource}.py"""

    # Build fields list for EndpointOperation
    fields_str = ", ".join(f'"{f}"' for f in res.writable_fields)

    # Build dataclass fields
    # All fields are Optional in the dataclass because the resource module pattern
    # constructs AnsibleClass(**{}) for the gathered state (list-all).
    # Required-ness is enforced by the module DOCUMENTATION argspec, not the dataclass.
    dc_lines = []
    for name in res.required_fields:
        meta = res.properties[name]
        hint = _py_type_hint(meta)
        dc_lines.append(f"    {name}: {hint} = None")

    for name in res.writable_fields:
        if name in res.required_fields:
            continue
        meta = res.properties[name]
        hint = _py_type_hint(meta)
        dc_lines.append(f"    {name}: {hint} = None")

    for name in res.read_only_fields:
        meta = res.properties.get(name, {"type": "Any", "nullable": True})
        hint = _py_type_hint({**meta, "nullable": True})
        dc_lines.append(f"    {name}: {hint} = None  # read-only")

    dc_body = "\n".join(dc_lines) if dc_lines else "    pass"

    # Build from_ansible_data body
    simple_fields = [f for f in res.writable_fields if f not in ("id",)]
    field_loop = "\n".join(f'        "{f}",' for f in simple_fields)

    # Build from_api body
    from_api_fields = "\n".join(f'            {f}=api_data.get("{f}"),' for f in list(res.writable_fields) + list(res.read_only_fields))

    # Build EndpointOperations
    ops = []
    if res.has_create:
        ops.append(f"""\
            "create": EndpointOperation(
                path="{res.list_path}",
                method="POST",
                fields=[{fields_str}],
                required_for="create",
                order=1,
            ),""")
    if res.has_update:
        ops.append(f"""\
            "update": EndpointOperation(
                path="{res.detail_path}",
                method="PATCH",
                fields=[{fields_str}],
                path_params=["id"],
                required_for="update",
                order=1,
            ),""")
    if res.has_delete:
        ops.append(f"""\
            "delete": EndpointOperation(
                path="{res.detail_path}",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),""")
    if res.has_get:
        ops.append(f"""\
            "get": EndpointOperation(
                path="{res.detail_path}",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),""")
    if res.has_list:
        ops.append(f"""\
            "list": EndpointOperation(
                path="{res.list_path}",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),""")
    ops_body = "\n".join(ops)

    return f'''\
"""
API v1 {res.class_prefix} dataclass and transform mixin.

Auto-generated by tools/generate_resource.py from the Gateway OpenAPI spec.
Review and customise before committing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext


@dataclass
class API{res.class_prefix}_v1(BaseTransformMixin):
    """API v1 representation of a gateway {res.name}."""

{dc_body}


class {res.class_prefix}TransformMixin_v1(BaseTransformMixin):
    """Transform mixin for {res.class_prefix} API v1."""

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "API{res.class_prefix}_v1":
        api_data: Dict[str, Any] = {{}}

        for field in (
{field_loop}
        ):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        for ro in {tuple(res.read_only_fields)!r}:
            val = getattr(ansible_instance, ro, None)
            if val is not None:
                api_data[ro] = val

        return API{res.class_prefix}_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {{
{ops_body}
        }}

    @classmethod
    def get_lookup_field(cls) -> str:
        return "{res.lookup_field}"

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ...ansible_models.{res.name} import Ansible{res.class_prefix}

        return Ansible{res.class_prefix}(
{from_api_fields}
        )
'''


def gen_ansible_model(res: ResourceSpec) -> str:
    """Generate plugins/plugin_utils/ansible_models/{resource}.py

    Now includes resource metadata (MODULE_NAME, CANONICAL_KEY, SYSTEM_KEY)
    for the resource module pattern.
    """

    dc_lines = []
    for name in res.required_fields:
        meta = res.properties[name]
        hint = _py_type_hint(meta)
        dc_lines.append(f"    {name}: {hint} = None")

    for name in res.writable_fields:
        if name in res.required_fields:
            continue
        meta = res.properties[name]
        hint = _py_type_hint(meta)
        dc_lines.append(f"    {name}: {hint} = None")

    dc_lines.append("")
    dc_lines.append("    # Read-only fields (populated from API)")
    for name in res.read_only_fields:
        meta = res.properties.get(name, {"type": "Any", "nullable": True})
        hint = _py_type_hint({**meta, "nullable": True})
        dc_lines.append(f"    {name}: {hint} = None")

    dc_body = "\n".join(dc_lines) if dc_lines else "    pass"

    return f'''\
"""
Ansible {res.class_prefix} dataclass — user-facing stable interface.

Auto-generated by tools/generate_resource.py from the Gateway OpenAPI spec.
"""

from dataclasses import dataclass
from typing import Optional, Union, Any, Dict, List

from ..platform.base_transform import BaseTransformMixin


@dataclass
class Ansible{res.class_prefix}(BaseTransformMixin):
    """Ansible representation of a gateway {res.name} (resource module pattern)."""

    # Resource metadata for the base action plugin
    MODULE_NAME = "{res.name}"
    CANONICAL_KEY = "{res.lookup_field}"
    SYSTEM_KEY = "id"
    SUPPORTS_DELETE = {res.has_delete}
    VALID_STATES = frozenset({{"merged", "replaced", "overridden", "deleted", "gathered"}})

{dc_body}
'''


def gen_module(res: ResourceSpec) -> str:
    """Generate plugins/modules/{resource}.py

    Uses the resource module pattern with config list and RM states.
    """

    # Build config suboptions block
    suboption_lines = []
    for name in res.required_fields:
        meta = res.properties[name]
        desc = meta.get("description") or f"The {name} of the {res.class_prefix}."
        # Quote descriptions containing colons to avoid YAML parse errors
        if ":" in desc:
            desc = f'"{desc}"'
        a_type = _ansible_type(meta["type"])
        suboption_lines.append(f"""\
        {name}:
          required: true
          type: {a_type}
          description: {desc}""")

    for name in res.writable_fields:
        if name in res.required_fields:
            continue
        meta = res.properties[name]
        desc = meta.get("description") or f"The {name} of the {res.class_prefix}."
        # Quote descriptions containing colons to avoid YAML parse errors
        if ":" in desc:
            desc = f'"{desc}"'
        a_type = _ansible_type(meta.get("type", "str"))
        suboption_lines.append(f"""\
        {name}:
          type: {a_type}
          description: {desc}""")

    # Add id as optional suboption (for update/delete by id)
    suboption_lines.append("""\
        id:
          type: str
          description: The unique identifier of the resource. Used for update/delete operations.""")

    subopts_block = "\n".join(suboption_lines)

    return f'''\
#!/usr/bin/python
# coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
Auto-generated by tools/generate_resource.py — review before committing.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: {res.name}
short_description: Manage gateway {res.name} resources.
description:
    - Create, update, delete, or gather automation platform gateway {res.name} resources.
    - Follows the Ansible resource module pattern with before/after state tracking.
options:
    config:
      description:
        - A list of {res.name} resource configurations.
        - Each entry represents a desired {res.name} state.
      type: list
      elements: dict
      suboptions:
{subopts_block}

extends_documentation_fragment:
  - ansible.platform.auth
  - ansible.platform.state
"""

EXAMPLES = """
- name: Create {res.name} resources (merged)
  ansible.platform.{res.name}:
    config:
      - {res.lookup_field}: "my-{res.name}"
    state: merged

- name: Gather current {res.name} state
  ansible.platform.{res.name}:
    state: gathered
  register: result

- name: Delete specific {res.name} resources
  ansible.platform.{res.name}:
    config:
      - {res.lookup_field}: "my-{res.name}"
    state: deleted

- name: Override — ensure only these {res.name} resources exist
  ansible.platform.{res.name}:
    config:
      - {res.lookup_field}: "keep-this-{res.name}"
    state: overridden
"""

RETURN = """
before:
  description: The state of the {res.name} resources before this run.
  returned: when state is not gathered
  type: list
  elements: dict
after:
  description: The state of the {res.name} resources after this run.
  returned: when state is not gathered
  type: list
  elements: dict
gathered:
  description: The gathered {res.name} resource state (read-only).
  returned: when state is gathered
  type: list
  elements: dict
config:
  description: The resulting configuration (alias for after or gathered).
  returned: always
  type: list
  elements: dict
"""
'''


def gen_action(res: ResourceSpec) -> str:
    """Generate plugins/action/{resource}.py

    Minimal: just set USER_MODEL. All CRUD+RM logic is in BaseResourceActionPlugin.
    """

    return f'''\
#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
Action plugin for ansible.platform.{res.name} resource module.

Auto-generated by tools/generate_resource.py — review before committing.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import (
    BaseResourceActionPlugin,
)


class ActionModule(BaseResourceActionPlugin):
    """Resource module action plugin for {res.name}."""

    USER_MODEL = "plugins.plugin_utils.ansible_models.{res.name}.Ansible{res.class_prefix}"
'''


def gen_integration_test(res: ResourceSpec) -> str:
    """Generate tests/integration/targets/{resource}_test/tasks/main.yml"""

    lf = res.lookup_field

    # Build create config items
    create_args_lines = [f'          {lf}: "{{{{ name_prefix }}}}-Test-{res.class_prefix}"']
    for name in res.required_fields:
        if name == lf:
            continue
        meta = res.properties[name]
        if meta["type"] == "str":
            create_args_lines.append(f'          {name}: "example-{name}"')
        elif meta["type"] == "int":
            create_args_lines.append(f"          {name}: 1  # TODO: set a valid value")
        elif meta["type"] == "bool":
            create_args_lines.append(f"          {name}: false")
    create_config = "\n".join(create_args_lines)

    return f"""\
---
# Integration tests for ansible.platform.{res.name} (resource module pattern)
# Auto-generated by tools/generate_resource.py — review and extend before committing.

- name: Generate a test ID
  ansible.builtin.set_fact:
    test_id: "{{{{ lookup('password', '/dev/null chars=ascii_letters length=16') }}}}"
  when: test_id is not defined

- name: Preset vars
  ansible.builtin.set_fact:
    name_prefix: "GW-Collection-Test-{res.class_prefix}-{{{{ test_id }}}}"

- name: Run Test
  module_defaults:
    group/ansible.platform.gateway:
      gateway_hostname: "{{{{ gateway_hostname }}}}"
      gateway_username: "{{{{ gateway_username }}}}"
      gateway_password: "{{{{ gateway_password }}}}"
      gateway_validate_certs: "{{{{ gateway_validate_certs | bool }}}}"

  block:
    - name: Gather existing state
      ansible.platform.{res.name}:
        state: gathered
      register: initial_state

    - name: Create {res.name} via merged
      ansible.platform.{res.name}:
        config:
{create_config}
        state: merged
      register: merged_result

    - name: Assert creation changed
      ansible.builtin.assert:
        that:
          - merged_result is changed
          - merged_result.after | length > 0

    - name: Re-apply merged (idempotency check)
      ansible.platform.{res.name}:
        config:
{create_config}
        state: merged
      register: idem_result

    - name: Assert no change on re-apply
      ansible.builtin.assert:
        that:
          - idem_result is not changed

    - name: Gather after create
      ansible.platform.{res.name}:
        state: gathered
      register: gathered_result

    - name: Assert gathered contains our resource
      ansible.builtin.assert:
        that:
          - gathered_result.gathered | length > 0

  always:
    - name: Delete {res.name} via deleted
      ansible.platform.{res.name}:
        config:
          - {lf}: "{{{{ name_prefix }}}}-Test-{res.class_prefix}"
        state: deleted
      when: merged_result is defined and merged_result is changed
...
"""


# ---------------------------------------------------------------------------
# File writing
# ---------------------------------------------------------------------------

FileSpec = Tuple[str, str]  # (relative_path, content)


def collect_files(res: ResourceSpec, collection_root: str) -> List[FileSpec]:
    """Return list of (relative_path, content) for all files to generate."""
    files: List[FileSpec] = [
        (
            f"plugins/plugin_utils/api/v1/{res.name}.py",
            gen_api_v1(res),
        ),
        (
            f"plugins/plugin_utils/ansible_models/{res.name}.py",
            gen_ansible_model(res),
        ),
        (
            f"plugins/modules/{res.name}.py",
            gen_module(res),
        ),
        (
            f"plugins/action/{res.name}.py",
            gen_action(res),
        ),
        (
            f"tests/integration/targets/{res.name}_test/tasks/main.yml",
            gen_integration_test(res),
        ),
    ]
    return files


def write_files(
    files: List[FileSpec],
    collection_root: str,
    dry_run: bool,
    overwrite: bool,
) -> None:
    for rel_path, content in files:
        abs_path = os.path.join(collection_root, rel_path)
        if os.path.exists(abs_path) and not overwrite:
            print(f"  SKIP   {rel_path}  (already exists; use --overwrite to replace)")
            continue
        if dry_run:
            print(f"  DRY    {rel_path}")
            print(indent(content[:400] + ("…" if len(content) > 400 else ""), "         "))
            print()
        else:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            print(f"  WROTE  {rel_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate boilerplate files for a new platform collection resource module.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--tag",
        required=False,
        default=None,
        help="OpenAPI tag to generate code for (e.g. 'services', 'http_ports')",
    )
    parser.add_argument(
        "--spec",
        default=os.path.join(
            os.path.dirname(__file__),
            "../../../aap-openapi-specs/gateway.json",
        ),
        help="Path to the OpenAPI JSON spec file",
    )
    parser.add_argument(
        "--collection-root",
        default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        help="Path to the collection root directory (default: parent of tools/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print what would be generated without writing files",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Overwrite existing files (default: skip)",
    )
    parser.add_argument(
        "--list-tags",
        action="store_true",
        default=False,
        help="List all available tags in the spec and exit",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Generate for ALL tags in the spec",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    spec_path = os.path.abspath(args.spec)
    if not os.path.isfile(spec_path):
        print(f"ERROR: spec file not found: {spec_path}", file=sys.stderr)
        return 2

    with open(spec_path, "r", encoding="utf-8") as fh:
        spec: Dict[str, Any] = json.load(fh)

    # Collect all tags
    all_tags: Set[str] = set()
    for path_item in spec.get("paths", {}).values():
        for op in path_item.values():
            if isinstance(op, dict):
                all_tags.update(op.get("tags", []))

    if args.list_tags or (args.tag is None and not args.all):
        print("Available tags in spec:")
        for t in sorted(all_tags):
            print(f"  {t}")
        return 0

    if args.all:
        tags_to_process = sorted(all_tags)
    else:
        tags_to_process = [args.tag]

    for tag in tags_to_process:
        if not get_paths_for_tag(spec, tag):
            print(f"WARNING: no paths found for tag '{tag}', skipping.", file=sys.stderr)
            continue

        res = ResourceSpec(tag, spec)
        print(res.summary())
        print()

        files = collect_files(res, args.collection_root)
        mode = "DRY RUN" if args.dry_run else "GENERATING"
        print(f"{mode} ({len(files)} files):\n")
        write_files(files, args.collection_root, dry_run=args.dry_run, overwrite=args.overwrite)
        print()

    if not args.dry_run:
        print(f"\nDone. Generated resource modules from {spec_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
