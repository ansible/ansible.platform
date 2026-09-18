# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for APIVersionRegistry (AAP-59525 / ANSTRAT-1640)."""

import shutil
import tempfile
from pathlib import Path

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry import (
    APIVersionRegistry,
)


def _make_fake_api_root():
    """Create a temporary api/ directory with service-scoped version stubs."""
    root = Path(tempfile.mkdtemp())
    (root / "gateway" / "v1").mkdir(parents=True)
    (root / "gateway" / "v2").mkdir(parents=True)
    (root / "gateway" / "v1" / "user.py").write_text("# stub\n")
    (root / "gateway" / "v2" / "user.py").write_text("# stub\n")
    (root / "gateway" / "v2" / "org.py").write_text("# stub\n")
    # Dirs/files that should be ignored by discovery
    (root / "gateway" / "v2" / "__init__.py").write_text("# init\n")
    (root / "gateway" / "v2" / "generated").write_text("# not a .py, ignored by glob anyway\n")
    return root


def test_discover_versions_populates_services_and_module_versions():
    """Discovery (run in __init__) populates services and module_versions from filesystem."""
    api_root = _make_fake_api_root()
    try:
        registry = APIVersionRegistry(api_base_path=str(api_root))

        assert "gateway" in registry.services
        assert "1" in registry.services["gateway"]
        assert "2" in registry.services["gateway"]
        assert registry.services["gateway"]["1"] == ["user"]
        assert sorted(registry.services["gateway"]["2"]) == ["org", "user"]

        assert "user" in registry.module_versions
        assert "org" in registry.module_versions
        assert sorted(registry.module_versions["user"]) == ["1", "2"]
        assert registry.module_versions["org"] == ["2"]

        assert registry.get_service_for_module("user") == "gateway"
        assert registry.get_service_for_module("org") == "gateway"
    finally:
        shutil.rmtree(api_root, ignore_errors=True)


def test_discover_multi_service():
    """Discovery finds modules across multiple services."""
    api_root = Path(tempfile.mkdtemp())
    try:
        (api_root / "gateway" / "v1").mkdir(parents=True)
        (api_root / "controller" / "v2").mkdir(parents=True)
        (api_root / "gateway" / "v1" / "user.py").write_text("# stub\n")
        (api_root / "controller" / "v2" / "job_template.py").write_text("# stub\n")

        registry = APIVersionRegistry(api_base_path=str(api_root))

        assert registry.get_service_for_module("user") == "gateway"
        assert registry.get_service_for_module("job_template") == "controller"
        assert registry.get_supported_versions("gateway") == ["1"]
        assert registry.get_supported_versions("controller") == ["2"]
        assert sorted(registry.get_services()) == ["controller", "gateway"]
    finally:
        shutil.rmtree(api_root, ignore_errors=True)


def test_find_best_version_exact_match():
    """find_best_version returns requested version when it exists for the module."""
    api_root = _make_fake_api_root()
    try:
        registry = APIVersionRegistry(api_base_path=str(api_root))

        assert registry.find_best_version("1", "user") == "1"
        assert registry.find_best_version("2", "user") == "2"
        assert registry.find_best_version("2", "org") == "2"
    finally:
        shutil.rmtree(api_root, ignore_errors=True)


def test_find_best_version_unknown_module_returns_none():
    """find_best_version returns None for a module not in any discovered version."""
    api_root = _make_fake_api_root()
    try:
        registry = APIVersionRegistry(api_base_path=str(api_root))

        assert registry.find_best_version("1", "nonexistent_module") is None
        assert registry.find_best_version("2", "nonexistent_module") is None
    finally:
        shutil.rmtree(api_root, ignore_errors=True)


def test_find_best_version_closest_lower():
    """find_best_version returns closest lower version when exact match missing."""
    api_root = _make_fake_api_root()
    try:
        registry = APIVersionRegistry(api_base_path=str(api_root))
        # user has versions 1 and 2; request 2.1 -> no exact, so closest lower is 2
        assert registry.find_best_version("2.1", "user") == "2"
    finally:
        shutil.rmtree(api_root, ignore_errors=True)
