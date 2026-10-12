"""Discover ansible.platform modules and extract DOCUMENTATION metadata.

Uses ast.parse() to extract DOCUMENTATION strings without importing the modules,
then resolves extends_documentation_fragment references to merge shared options.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Auth-related options that are server-level config, not per-tool parameters
_AUTH_OPTION_NAMES = frozenset(
    {
        "aap_hostname",
        "aap_username",
        "aap_password",
        "aap_token",
        "aap_validate_certs",
        "aap_request_timeout",
        "gateway_hostname",
        "gateway_username",
        "gateway_password",
        "gateway_token",
        "gateway_validate_certs",
        "gateway_request_timeout",
        "validate_certs",
        "request_timeout",
        "persistent_manager_idle_timeout",
    }
)


@dataclass
class ModuleInfo:
    """Parsed metadata for a single ansible.platform module."""

    name: str
    short_description: str
    description: str
    options: dict[str, Any] = field(default_factory=dict)
    has_state: bool = False


def _extract_string_constant(source: str, var_name: str) -> str | None:
    """Extract a module-level string constant via AST without importing."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == var_name:
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return node.value.value
    return None


def _load_doc_fragment(fragment_name: str, doc_fragments_dir: Path) -> dict[str, Any]:
    """Load options from a documentation fragment file.

    Args:
        fragment_name: Fragment reference (e.g. 'ansible.platform.auth')
        doc_fragments_dir: Path to plugins/doc_fragments/

    Returns:
        Options dict from the fragment, or empty dict.
    """
    if "." in fragment_name:
        parts = fragment_name.split(".")
        frag_file = parts[-1]
    else:
        frag_file = fragment_name

    frag_path = doc_fragments_dir / f"{frag_file}.py"
    if not frag_path.exists():
        logger.debug("Fragment file not found: %s", frag_path)
        return {}

    source = frag_path.read_text(encoding="utf-8")
    doc_string = _extract_string_constant(source, "DOCUMENTATION")
    if not doc_string:
        # Fragments use class-level DOCUMENTATION; parse the class body
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) and target.id == "DOCUMENTATION":
                                if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                                    doc_string = item.value.value
                                    break

    if not doc_string:
        return {}

    try:
        parsed = yaml.safe_load(doc_string)
    except yaml.YAMLError:
        return {}

    return parsed.get("options", {}) if isinstance(parsed, dict) else {}


def discover_modules(collection_root: Path | None = None) -> dict[str, ModuleInfo]:
    """Discover all ansible.platform modules and extract their metadata.

    Args:
        collection_root: Path to the collection root. Auto-detected if None.

    Returns:
        Dict mapping module name to ModuleInfo.
    """
    if collection_root is None:
        # Auto-detect: walk up from this file to find galaxy.yml
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "galaxy.yml").exists():
                collection_root = parent
                break
        if collection_root is None:
            raise FileNotFoundError(
                "Cannot auto-detect collection root. "
                "Ensure the MCP server is run from within the ansible.platform repository "
                "or pass collection_root explicitly."
            )

    modules_dir = collection_root / "plugins" / "modules"
    doc_fragments_dir = collection_root / "plugins" / "doc_fragments"

    if not modules_dir.is_dir():
        raise FileNotFoundError(f"Modules directory not found: {modules_dir}")

    # Pre-load all doc fragments
    fragment_cache: dict[str, dict[str, Any]] = {}

    modules: dict[str, ModuleInfo] = {}

    for module_path in sorted(modules_dir.glob("*.py")):
        if module_path.name.startswith("_") or module_path.name == "__init__.py":
            continue

        module_name = module_path.stem
        source = module_path.read_text(encoding="utf-8")
        doc_string = _extract_string_constant(source, "DOCUMENTATION")

        if not doc_string:
            logger.debug("No DOCUMENTATION in %s, skipping", module_path.name)
            continue

        try:
            doc_data = yaml.safe_load(doc_string)
        except yaml.YAMLError as exc:
            logger.warning("Failed to parse DOCUMENTATION in %s: %s", module_path.name, exc)
            continue

        if not isinstance(doc_data, dict):
            continue

        # Merge doc fragment options first, then module options (module wins)
        merged_options: dict[str, Any] = {}
        fragments = doc_data.get("extends_documentation_fragment", [])
        if isinstance(fragments, str):
            fragments = [fragments]

        for frag_name in fragments:
            if frag_name not in fragment_cache:
                fragment_cache[frag_name] = _load_doc_fragment(frag_name, doc_fragments_dir)
            merged_options.update(fragment_cache[frag_name])

        module_options = doc_data.get("options", {})
        if isinstance(module_options, dict):
            merged_options.update(module_options)

        # Strip auth options -- these are server-level config
        tool_options = {k: v for k, v in merged_options.items() if k not in _AUTH_OPTION_NAMES}

        # Build description from list or string
        raw_desc = doc_data.get("description", [])
        if isinstance(raw_desc, list):
            description = " ".join(str(d) for d in raw_desc)
        else:
            description = str(raw_desc)

        has_state = "state" in tool_options

        modules[module_name] = ModuleInfo(
            name=module_name,
            short_description=doc_data.get("short_description", f"Manage {module_name} resources"),
            description=description,
            options=tool_options,
            has_state=has_state,
        )

    logger.info("Discovered %d modules", len(modules))
    return modules
