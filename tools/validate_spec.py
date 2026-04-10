"""
Validate all EndpointOperation declarations in api/v1/*.py against the
Gateway OpenAPI specification.

Usage (from the collection root):
    python tools/validate_spec.py \\
        --spec ../aap-openapi-specs/2.6/gateway.json \\
        [--api-dir plugins/plugin_utils/api/v1]

Exit codes:
    0  all checks passed
    1  one or more validation errors found
    2  usage / IO error
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class OperationRecord(NamedTuple):
    module_file: str  # relative path to the api/v1 file
    class_name: str  # e.g. ServiceTransformMixin_v1
    op_name: str  # key in get_endpoint_operations dict (create/update/…)
    path: str  # declared path
    method: str  # declared HTTP method (uppercase)
    fields: List[str]  # body field names declared in fields=[…]
    line: int  # line number in source file (for error messages)


class ValidationError(NamedTuple):
    module_file: str
    class_name: str
    op_name: str
    path: str
    method: str
    message: str
    line: int


# ---------------------------------------------------------------------------
# AST extraction
# ---------------------------------------------------------------------------


def _ast_constant(node: ast.expr) -> Optional[Any]:
    """Return the Python value of a constant AST node, or None."""
    if isinstance(node, ast.Constant):
        return node.value
    # Python 3.7 compatibility
    if isinstance(node, ast.Str):
        return node.s  # type: ignore[attr-defined]
    return None


def _ast_string_list(node: ast.expr) -> Optional[List[str]]:
    """Return list of strings from an ast.List node, or None if not parseable."""
    if not isinstance(node, ast.List):
        return None
    result = []
    for elt in node.elts:
        val = _ast_constant(elt)
        if isinstance(val, str):
            result.append(val)
    return result


def _extract_endpoint_operation(call_node: ast.Call, source_line: int) -> Optional[Dict[str, Any]]:
    """
    Parse an EndpointOperation(…) call AST node into a plain dict.

    Only extracts keyword arguments (positional args are not used in practice).
    """
    record: Dict[str, Any] = {"line": source_line}
    for kw in call_node.keywords:
        if kw.arg == "path":
            val = _ast_constant(kw.value)
            if isinstance(val, str):
                record["path"] = val
        elif kw.arg == "method":
            val = _ast_constant(kw.value)
            if isinstance(val, str):
                record["method"] = val.upper()
        elif kw.arg == "fields":
            lst = _ast_string_list(kw.value)
            if lst is not None:
                record["fields"] = lst
    return record if ("path" in record and "method" in record) else None


def extract_operations_from_file(filepath: str) -> List[OperationRecord]:
    """
    Parse a single api/v1/*.py file and return all EndpointOperation records.
    """
    with open(filepath, "r", encoding="utf-8") as fh:
        source = fh.read()

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        print(f"  WARNING: cannot parse {filepath}: {exc}", file=sys.stderr)
        return []

    records: List[OperationRecord] = []
    rel_path = filepath  # caller can pass a relative path for nicer output

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        class_name = node.name

        for item in node.body:
            if not (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "get_endpoint_operations"):
                continue

            # Walk the method body looking for Return with a Dict value
            for stmt in ast.walk(item):
                if not (isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Dict)):
                    continue

                dict_node: ast.Dict = stmt.value
                for key_node, val_node in zip(dict_node.keys, dict_node.values):
                    op_name = _ast_constant(key_node)
                    if not isinstance(op_name, str):
                        continue

                    # The value may be an EndpointOperation(…) call directly,
                    # or it could be a variable reference we cannot resolve
                    # statically — skip non-Call nodes silently.
                    if not isinstance(val_node, ast.Call):
                        continue

                    extracted = _extract_endpoint_operation(val_node, val_node.lineno)
                    if extracted is None:
                        continue

                    records.append(
                        OperationRecord(
                            module_file=rel_path,
                            class_name=class_name,
                            op_name=op_name,
                            path=extracted["path"],
                            method=extracted["method"],
                            fields=extracted.get("fields", []),
                            line=extracted["line"],
                        )
                    )
    return records


def collect_all_operations(api_dir: str) -> List[OperationRecord]:
    """Scan every *.py file in *api_dir* and return all OperationRecords."""
    all_records: List[OperationRecord] = []
    for fname in sorted(os.listdir(api_dir)):
        if not fname.endswith(".py") or fname.startswith("__"):
            continue
        fpath = os.path.join(api_dir, fname)
        ops = extract_operations_from_file(fpath)
        if ops:
            # Make path relative to cwd for cleaner output
            try:
                fpath_display = os.path.relpath(fpath)
            except ValueError:
                fpath_display = fpath
            all_records.extend(op._replace(module_file=fpath_display) for op in ops)
    return all_records


# ---------------------------------------------------------------------------
# Spec indexing
# ---------------------------------------------------------------------------


def _resolve_ref(spec: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Follow a single $ref to components/schemas."""
    ref = schema.get("$ref", "")
    if ref.startswith("#/components/schemas/"):
        name = ref.split("/")[-1]
        return spec.get("components", {}).get("schemas", {}).get(name, {})
    return schema


def _collect_properties(spec: Dict[str, Any], schema: Dict[str, Any], depth: int = 0) -> Set[str]:
    """
    Recursively collect all property names from a JSON Schema object,
    handling $ref, allOf, anyOf, oneOf, and direct properties.
    """
    if depth > 8:
        return set()  # guard against infinite recursion

    # Resolve top-level $ref first
    if "$ref" in schema:
        schema = _resolve_ref(spec, schema)

    result: Set[str] = set()

    # Direct properties
    for name in schema.get("properties", {}).keys():
        result.add(name)

    # allOf / anyOf / oneOf — merge all sub-schemas
    for combiner in ("allOf", "anyOf", "oneOf"):
        for sub in schema.get(combiner, []):
            result |= _collect_properties(spec, sub, depth + 1)

    return result


def _body_fields(spec: Dict[str, Any], path: str, method: str) -> Optional[Set[str]]:
    """
    Return the set of property names declared in the request body schema for
    (path, method).  Returns None if there is no requestBody.
    Handles $ref, allOf, anyOf, oneOf recursively.
    """
    path_item = spec.get("paths", {}).get(path, {})
    op = path_item.get(method.lower(), {})
    if not op:
        return None
    req_body = op.get("requestBody", {})
    content = req_body.get("content", {})
    schema = content.get("application/json", {}).get("schema", {}) or content.get("application/x-www-form-urlencoded", {}).get("schema", {})
    if not schema:
        return None
    props = _collect_properties(spec, schema)
    return props if props else set()


def build_spec_index(spec: Dict[str, Any]) -> Dict[Tuple[str, str], Optional[Set[str]]]:
    """
    Build a mapping of (path, METHOD) → body_fields_set (or None if no body).
    """
    index: Dict[Tuple[str, str], Optional[Set[str]]] = {}
    for path, path_item in spec.get("paths", {}).items():
        for method_lower, op in path_item.items():
            if not isinstance(op, dict):
                continue
            method = method_lower.upper()
            fields = _body_fields(spec, path, method)
            index[(path, method)] = fields
    return index


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

# Methods that carry a request body; for others we skip field checks.
_WRITE_METHODS = {"POST", "PUT", "PATCH"}

# Paths that intentionally deviate from the spec (document known exceptions).
# Format: frozenset of (path, METHOD) tuples.
_KNOWN_EXCEPTIONS: frozenset = frozenset(
    {
        # /settings/all/ is a convenience endpoint not in the Gateway OpenAPI spec.
        # The canonical spec path is /settings/{category_slug}/.
        # TODO: migrate SettingsTransformMixin_v1 to use the canonical endpoint.
        ("/api/gateway/v1/settings/all/", "GET"),
        ("/api/gateway/v1/settings/all/", "PUT"),
    }
)


def validate(
    operations: List[OperationRecord],
    spec_index: Dict[Tuple[str, str], Optional[Set[str]]],
    spec: Dict[str, Any],
    known_exceptions: frozenset = _KNOWN_EXCEPTIONS,
) -> List[ValidationError]:
    errors: List[ValidationError] = []
    _warnings: List[str] = []

    # Build a set of all (path, method) pairs in the spec for fast lookup
    spec_pairs = set(spec_index.keys())

    for op in operations:
        key = (op.path, op.method)

        # Known exceptions — skip silently (noted in _KNOWN_EXCEPTIONS docstring)
        if key in known_exceptions:
            continue

        # 1. Path must exist in spec
        spec_path_methods = {m for (p, m) in spec_pairs if p == op.path}
        if not spec_path_methods:
            # Try to find near-matches for better diagnostics
            similar = [p for p in spec.get("paths", {}) if op.path.rstrip("/") in p]
            hint = ""
            if similar:
                hint = f" (similar spec paths: {', '.join(similar[:3])})"
            errors.append(
                ValidationError(
                    module_file=op.module_file,
                    class_name=op.class_name,
                    op_name=op.op_name,
                    path=op.path,
                    method=op.method,
                    message=f"Path not found in spec{hint}",
                    line=op.line,
                )
            )
            continue

        # 2. HTTP method must be allowed at that path
        if op.method not in spec_path_methods:
            allowed = ", ".join(sorted(spec_path_methods))
            errors.append(
                ValidationError(
                    module_file=op.module_file,
                    class_name=op.class_name,
                    op_name=op.op_name,
                    path=op.path,
                    method=op.method,
                    message=(f"Method {op.method} not in spec for this path (allowed: {allowed})"),
                    line=op.line,
                )
            )
            continue

        # 3. For write operations with declared fields, check all fields are in spec
        if op.method in _WRITE_METHODS and op.fields:
            spec_fields = spec_index.get(key)
            if spec_fields is not None:
                unknown = sorted(set(op.fields) - spec_fields)
                if unknown:
                    errors.append(
                        ValidationError(
                            module_file=op.module_file,
                            class_name=op.class_name,
                            op_name=op.op_name,
                            path=op.path,
                            method=op.method,
                            message=(f"Field(s) declared in EndpointOperation.fields not found in spec request body schema: {unknown}"),
                            line=op.line,
                        )
                    )

    return errors


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _fmt_location(err: ValidationError) -> str:
    return f"{err.module_file}:{err.line} [{err.class_name}.get_endpoint_operations → '{err.op_name}']"


def report(
    errors: List[ValidationError],
    operations: List[OperationRecord],
    show_summary: bool = True,
    known_exceptions: frozenset = _KNOWN_EXCEPTIONS,
) -> None:
    if errors:
        print(f"\n{'=' * 70}")
        print(f"  SPEC VALIDATION FAILED — {len(errors)} error(s) found")
        print(f"{'=' * 70}\n")

        # Group by file for readability
        by_file: Dict[str, List[ValidationError]] = defaultdict(list)
        for err in errors:
            by_file[err.module_file].append(err)

        for fpath, file_errors in sorted(by_file.items()):
            print(f"  {fpath}")
            for err in file_errors:
                loc = f"line {err.line} [{err.class_name} / '{err.op_name}']"
                print(f"    ✗  {err.method} {err.path}")
                print(f"       {loc}")
                print(f"       {err.message}")
            print()
    else:
        print(f"\n  ✓  All {len(operations)} EndpointOperation(s) validated against spec.\n")

    if show_summary:
        # Print known exceptions as informational
        exc_count = sum(1 for op in operations if (op.path, op.method) in known_exceptions)
        if exc_count:
            print(
                f"  ℹ  {exc_count} operation(s) skipped (listed in _KNOWN_EXCEPTIONS):\n"
                + "\n".join(f"     {op.method} {op.path}  ({op.module_file})" for op in operations if (op.path, op.method) in known_exceptions)
                + "\n"
            )


# ---------------------------------------------------------------------------
# Coverage report (optional)
# ---------------------------------------------------------------------------


def coverage_report(
    operations: List[OperationRecord],
    spec: Dict[str, Any],
) -> None:
    """Print a table of which spec paths are/aren't covered by any module."""
    covered: Set[str] = set()
    for op in operations:
        covered.add(op.path)

    all_spec_paths = set(spec.get("paths", {}).keys())
    # Only report resource paths (skip root/version discovery paths)
    resource_paths = {p for p in all_spec_paths if p.startswith("/api/gateway/v1/") and p not in ("/api/", "/api/gateway/", "/api/gateway/v1/")}

    uncovered = sorted(resource_paths - covered)
    print(f"\n  Coverage: {len(covered & resource_paths)}/{len(resource_paths)} spec paths have a module.\n")
    if uncovered:
        print("  Uncovered spec paths (no EndpointOperation declared):")
        for p in uncovered:
            methods = sorted(spec["paths"][p].keys())
            print(f"    {p}  [{', '.join(m.upper() for m in methods)}]")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate EndpointOperation declarations against an OpenAPI spec.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--spec",
        default=os.path.join(
            os.path.dirname(__file__),
            "../../../aap-openapi-specs/2.6/gateway.json",
        ),
        help="Path to the OpenAPI JSON spec file (default: ../aap-openapi-specs/2.6/gateway.json)",
    )
    parser.add_argument(
        "--api-dir",
        default=os.path.join(
            os.path.dirname(__file__),
            "../plugins/plugin_utils/api/v1",
        ),
        help="Directory containing api/v1/*.py transform files",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        default=False,
        help="Also print a coverage report of spec paths vs declared modules",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Treat _KNOWN_EXCEPTIONS as errors too (useful for planned migrations)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    # -- Load spec --------------------------------------------------------
    spec_path = os.path.abspath(args.spec)
    if not os.path.isfile(spec_path):
        print(f"ERROR: spec file not found: {spec_path}", file=sys.stderr)
        return 2

    with open(spec_path, "r", encoding="utf-8") as fh:
        spec: Dict[str, Any] = json.load(fh)

    # -- Find api/v1 dir --------------------------------------------------
    api_dir = os.path.abspath(args.api_dir)
    if not os.path.isdir(api_dir):
        print(f"ERROR: api-dir not found: {api_dir}", file=sys.stderr)
        return 2

    # -- Extract operations -----------------------------------------------
    print(f"Scanning {api_dir} …")
    operations = collect_all_operations(api_dir)
    print(f"Found {len(operations)} EndpointOperation(s) across {len({op.module_file for op in operations})} file(s).")

    if not operations:
        print("WARNING: no EndpointOperation records found — check --api-dir.", file=sys.stderr)
        return 2

    # -- Build spec index -------------------------------------------------
    print(f"Loading spec: {spec_path}")
    spec_index = build_spec_index(spec)
    print(f"Spec contains {len(spec_index)} path+method pair(s) across {len(spec.get('paths', {}))} path(s).\n")

    # -- Validate ---------------------------------------------------------
    effective_exceptions = frozenset() if args.strict else _KNOWN_EXCEPTIONS
    errors = validate(operations, spec_index, spec, known_exceptions=effective_exceptions)

    report(errors, operations, known_exceptions=effective_exceptions)

    # -- Coverage ---------------------------------------------------------
    if args.coverage:
        coverage_report(operations, spec)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
