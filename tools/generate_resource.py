"""
Generate boilerplate files for a new platform collection resource from the
Gateway OpenAPI specification.

Usage (from the collection root):
    python tools/generate_resource.py \\
        --tag services \\
        --spec ../aap-openapi-specs/2.6/gateway.json \\
        [--dry-run]

For each resource tag the generator creates (unless the file already exists):
    plugins/plugin_utils/api/v1/{resource}.py          – TransformMixin + API dataclass
    plugins/plugin_utils/ansible_models/{resource}.py  – AnsibleModel dataclass
    plugins/modules/{resource}.py                      – Module with DOCUMENTATION
    plugins/action/{resource}.py                       – Action plugin
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
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Code generators
# ---------------------------------------------------------------------------


def _py_type_hint(meta: Dict[str, Any]) -> str:
    base = meta.get("type", "Any")
    if meta.get("nullable") or not meta.get("required"):
        return f"Optional[{base}]"
    return base


def gen_api_v1(res: ResourceSpec) -> str:
    """Generate plugins/plugin_utils/api/v1/{resource}.py"""

    # Build fields list for EndpointOperation
    fields_str = ", ".join(f'"{f}"' for f in res.writable_fields)

    # Build dataclass fields
    dc_lines = []
    for name in res.required_fields:
        meta = res.properties[name]
        py_type = meta["type"]
        dc_lines.append(f"    {name}: {py_type}")

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
    """Generate plugins/plugin_utils/ansible_models/{resource}.py"""

    dc_lines = []
    for name in res.required_fields:
        meta = res.properties[name]
        dc_lines.append(f"    {name}: {meta['type']}")

    for name in res.writable_fields:
        if name in res.required_fields:
            continue
        meta = res.properties[name]
        hint = _py_type_hint(meta)
        dc_lines.append(f"    {name}: {hint} = None")

    dc_lines.append('    state: str = "present"')
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


@dataclass
class Ansible{res.class_prefix}:
    """Ansible representation of a gateway {res.name}."""

{dc_body}
'''


def gen_module(res: ResourceSpec) -> str:
    """Generate plugins/modules/{resource}.py"""

    # Build DOCUMENTATION options block
    opt_lines = []
    for name in res.required_fields:
        meta = res.properties[name]
        desc = meta.get("description") or f"The {name} of the {res.class_prefix}."
        py_type = meta["type"]
        ansible_type = {"int": "int", "bool": "bool", "float": "float"}.get(py_type, "str")
        opt_lines.append(f"""\
    {name}:
      required: true
      type: {ansible_type}
      description: {desc}""")

    for name in res.writable_fields:
        if name in res.required_fields:
            continue
        meta = res.properties[name]
        desc = meta.get("description") or f"The {name} of the {res.class_prefix}."
        py_type = meta.get("type", "str")
        ansible_type = {"int": "int", "bool": "bool", "float": "float"}.get(py_type, "str")
        opt_lines.append(f"""\
    {name}:
      type: {ansible_type}
      description: {desc}""")

    opt_lines.append("""\
    state:
      description:
        - Desired state of the resource.
        - C(present) ensures the resource exists.
        - C(absent) removes the resource.
        - C(exists) returns exists=True/False without making changes.
      type: str
      default: present
      choices: [present, absent, exists]""")

    opts_block = "\n".join(opt_lines)

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
short_description: Manage a gateway {res.name}.
description:
    - Create, update, or delete an automation platform gateway {res.name}.
options:
{opts_block}

extends_documentation_fragment:
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Create a {res.name}
  ansible.platform.{res.name}:
    {res.lookup_field}: "my-{res.name}"
    state: present

- name: Delete a {res.name}
  ansible.platform.{res.name}:
    {res.lookup_field}: "my-{res.name}"
    state: absent
"""

RETURN = """
{res.name}:
  description: The {res.name} resource data.
  returned: always
  type: dict
"""
'''


def gen_action(res: ResourceSpec) -> str:
    """Generate plugins/action/{resource}.py"""

    return f'''\
#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
Action plugin for ansible.platform.{res.name} module.

Auto-generated by tools/generate_resource.py — review before committing.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
import time
from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.{res.name} import (
    Ansible{res.class_prefix},
)

logger = logging.getLogger(__name__)

_AUTH_PARAMS = (
    "gateway_hostname", "gateway_username", "gateway_password",
    "gateway_token", "gateway_validate_certs", "gateway_request_timeout",
    "aap_hostname", "aap_username", "aap_password", "aap_token",
    "aap_validate_certs", "aap_request_timeout",
)


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for {res.name} module."""

    MODULE_NAME = "{res.name}"

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        self._task_vars = task_vars
        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp

        action_start = time.perf_counter()

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                from ansible.errors import AnsibleError
                raise AnsibleError(
                    "Could not load DOCUMENTATION for {res.name} module"
                )

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            validated_params = validated_input.validated_parameters
            resource_data = {{
                k: v for k, v in validated_params.items()
                if v is not None and k not in _AUTH_PARAMS
            }}
            resource = Ansible{res.class_prefix}(**resource_data)
            operation = self._detect_operation(validated_params)
            state = validated_params.get("state", "present")

            # --- exists check ------------------------------------------------
            if state == "exists":
                try:
                    find_result = manager.execute(
                        operation="find",
                        module_name=self.MODULE_NAME,
                        ansible_data={{"{res.lookup_field}": getattr(resource, "{res.lookup_field}")}},
                    )
                    exists = bool(find_result and find_result.get("id"))
                except Exception:
                    exists = False
                result.update({{
                    "changed": False,
                    "failed": False,
                    "exists": exists,
                    self.MODULE_NAME: find_result if exists else {{}},
                }})
                return result

            # --- idempotent create -------------------------------------------
            if operation == "create" and state == "present":
                try:
                    find_result = manager.execute(
                        operation="find",
                        module_name=self.MODULE_NAME,
                        ansible_data={{"{res.lookup_field}": getattr(resource, "{res.lookup_field}")}},
                    )
                    if find_result and find_result.get("id"):
                        operation = "update"
                        resource.id = find_result.get("id")
                except Exception:
                    pass

            # --- delete: look up id if missing --------------------------------
            if operation == "delete" and not resource.id:
                try:
                    find_result = manager.execute(
                        operation="find",
                        module_name=self.MODULE_NAME,
                        ansible_data={{"{res.lookup_field}": getattr(resource, "{res.lookup_field}")}},
                    )
                    if find_result and find_result.get("id"):
                        resource.id = find_result.get("id")
                    else:
                        result.update({{
                            "changed": False,
                            "failed": False,
                            self.MODULE_NAME: {{"state": "absent"}},
                            "msg": "{res.class_prefix} '%s' does not exist (already absent)"
                            % getattr(resource, "{res.lookup_field}", ""),
                        }})
                        return result
                except Exception:
                    result.update({{
                        "changed": False,
                        "failed": False,
                        self.MODULE_NAME: {{"state": "absent"}},
                        "msg": "{res.class_prefix} '%s' does not exist (already absent)"
                        % getattr(resource, "{res.lookup_field}", ""),
                    }})
                    return result

            if operation == "enforced":
                operation = "update"

            ansible_data = asdict(resource)
            if operation == "update" and state == "enforced":
                ansible_data["_platform_enforced"] = True

            # --- check mode --------------------------------------------------
            if self._task.check_mode and operation in ("create", "update", "delete"):
                if operation == "delete":
                    result.update({{
                        "changed": bool(resource.id),
                        "failed": False,
                        self.MODULE_NAME: {{"state": "absent"}},
                    }})
                else:
                    result.update({{
                        "changed": True,
                        "failed": False,
                        self.MODULE_NAME: {{
                            "{res.lookup_field}": getattr(resource, "{res.lookup_field}")
                        }},
                    }})
                return result

            # --- execute -----------------------------------------------------
            api_result = manager.execute(
                operation=operation,
                module_name=self.MODULE_NAME,
                ansible_data=ansible_data,
            )

            elapsed = time.perf_counter() - action_start
            logger.debug("{{}} {{}} completed in {{:.3f}}s".format(
                self.MODULE_NAME, operation, elapsed
            ))

            changed = operation in ("create", "update", "delete")
            result.update({{
                "changed": changed,
                "failed": False,
                self.MODULE_NAME: api_result or {{}},
            }})

        except Exception as exc:
            result.update({{
                "changed": False,
                "failed": True,
                "msg": str(exc),
            }})

        return result
'''


def gen_integration_test(res: ResourceSpec) -> str:
    """Generate tests/integration/targets/{resource}_test/tasks/main.yml"""

    # Pick the first required field as the lookup key
    lf = res.lookup_field

    # Build create args
    create_args_lines = [f'    {lf}: "{{{{ name_prefix }}}}-Test-{res.class_prefix}"']
    for name in res.required_fields:
        if name == lf:
            continue
        meta = res.properties[name]
        if meta["type"] == "str":
            create_args_lines.append(f'    {name}: "example-{name}"')
        elif meta["type"] == "int":
            create_args_lines.append(f"    {name}: 1  # TODO: set a valid value")
        elif meta["type"] == "bool":
            create_args_lines.append(f"    {name}: false")
    create_args = "\n".join(create_args_lines)

    return f'''\
---
# Integration tests for ansible.platform.{res.name}
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
    - name: Create {res.name}
      ansible.platform.{res.name}:
{create_args}
        state: present
      register: created_{res.name}

    - name: Assert creation changed
      ansible.builtin.assert:
        that:
          - created_{res.name} is changed
          - created_{res.name}.{res.name}.{lf} is defined

    - name: Check idempotency (re-apply, expect no change)
      ansible.platform.{res.name}:
{create_args}
        state: present
      register: idempotent_{res.name}

    - name: Assert no change on re-apply
      ansible.builtin.assert:
        that:
          - idempotent_{res.name} is not changed

    - name: Check exists returns true
      ansible.platform.{res.name}:
        {lf}: "{{{{ created_{res.name}.{res.name}.{lf} }}}}"
        state: exists
      register: exists_check

    - name: Assert exists is true
      ansible.builtin.assert:
        that:
          - exists_check.exists

  always:
    - name: Delete {res.name}
      ansible.platform.{res.name}:
        {lf}: "{{{{ created_{res.name}.{res.name}.{lf} }}}}"
        state: absent
      when: >-
        created_{res.name} is defined
        and "{res.name}" in created_{res.name}
        and "{lf}" in created_{res.name}.{res.name}
...
'''


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
            status = "WROTE  " if not os.path.exists(abs_path) else "WROTE  "
            print(f"  {status}{rel_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate boilerplate files for a new platform collection resource.",
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
            "../../../aap-openapi-specs/2.6/gateway.json",
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
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    spec_path = os.path.abspath(args.spec)
    if not os.path.isfile(spec_path):
        print(f"ERROR: spec file not found: {spec_path}", file=sys.stderr)
        return 2

    with open(spec_path, "r", encoding="utf-8") as fh:
        spec: Dict[str, Any] = json.load(fh)

    if args.list_tags or args.tag is None:
        all_tags: Set[str] = set()
        for path_item in spec.get("paths", {}).values():
            for op in path_item.values():
                if isinstance(op, dict):
                    all_tags.update(op.get("tags", []))
        print("Available tags in spec:")
        for t in sorted(all_tags):
            print(f"  {t}")
        return 0

    tag = args.tag
    if not get_paths_for_tag(spec, tag):
        print(f"ERROR: no paths found for tag '{tag}' in spec.", file=sys.stderr)
        print("Run with --list-tags to see available tags.", file=sys.stderr)
        return 2

    res = ResourceSpec(tag, spec)
    print(res.summary())
    print()

    files = collect_files(res, args.collection_root)
    mode = "DRY RUN" if args.dry_run else "GENERATING"
    print(f"{mode} ({len(files)} files):\n")
    write_files(files, args.collection_root, dry_run=args.dry_run, overwrite=args.overwrite)

    if not args.dry_run:
        print(f"\nDone. Run the spec validator to confirm:\n  python tools/validate_spec.py --spec {args.spec}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
