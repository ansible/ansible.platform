"""API version registry for dynamic version discovery.

This module provides filesystem-based discovery of available API versions
and module implementations, scoped by service (gateway, controller, etc.).
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from packaging import version
except ImportError:
    import re

    class SimpleVersion:
        """Simple version parser for basic version comparison."""

        def __init__(self, version_str: str):
            self.version_str = version_str
            parts = re.findall(r"\d+", version_str)
            self.parts = [int(p) for p in parts] if parts else [0]

        def __le__(self, other):
            return self.parts <= other.parts

        def __lt__(self, other):
            return self.parts < other.parts

        def __gt__(self, other):
            return self.parts > other.parts

    def version_parse(v: str):
        return SimpleVersion(v)

    version = type("version", (), {"parse": version_parse})()


DEFAULT_SERVICE = "gateway"


class APIVersionRegistry:
    """
    Registry that discovers and manages API version information.

    Scans the api/{service}/v{version}/ directory structure to find
    available services, versions, and module implementations.

    Attributes:
        api_base_path: Path to api/ directory containing service directories
        ansible_models_path: Path to ansible_models/ with stable interfaces
        services: Dict mapping service -> {version -> [modules]}
        module_service: Dict mapping module_name -> service
    """

    def __init__(self, api_base_path: Optional[str] = None, ansible_models_path: Optional[str] = None):
        if api_base_path is None:
            current_file = Path(__file__)
            plugin_utils = current_file.parent.parent
            api_base_path = str(plugin_utils / "api")

        if ansible_models_path is None:
            current_file = Path(__file__)
            plugin_utils = current_file.parent.parent
            ansible_models_path = str(plugin_utils / "ansible_models")

        self.api_base_path = Path(api_base_path)
        self.ansible_models_path = Path(ansible_models_path)

        self.services: Dict[str, Dict[str, List[str]]] = {}
        self.module_service: Dict[str, str] = {}
        self.module_versions: Dict[str, List[str]] = {}

        self._discover_versions()

    def _discover_versions(self) -> None:
        """Scan filesystem to discover services, API versions, and modules."""
        if not self.api_base_path.exists():
            logger.warning("API base path not found: %s", self.api_base_path)
            return

        for service_dir in self.api_base_path.iterdir():
            if not service_dir.is_dir():
                continue
            if service_dir.name.startswith("_"):
                continue

            service_name = service_dir.name
            self.services[service_name] = {}

            for version_dir in service_dir.iterdir():
                if not version_dir.is_dir():
                    continue
                if not version_dir.name.startswith("v"):
                    continue

                version_str = version_dir.name[1:].replace("_", ".")

                module_files = [f for f in version_dir.glob("*.py") if not f.name.startswith("_") and f.name != "generated"]
                module_names = [f.stem for f in module_files]

                self.services[service_name][version_str] = module_names

                for module_name in module_names:
                    self.module_service[module_name] = service_name
                    if module_name not in self.module_versions:
                        self.module_versions[module_name] = []
                    self.module_versions[module_name].append(version_str)

            for module_name in self.module_versions:
                self.module_versions[module_name].sort(key=version.parse)

        logger.info(
            "Discovered services: %s",
            {s: sorted(v.keys(), key=version.parse) for s, v in self.services.items()},
        )

    def get_service_for_module(self, module_name: str) -> Optional[str]:
        """Get the service a module belongs to."""
        return self.module_service.get(module_name)

    def get_services(self) -> List[str]:
        """Get all discovered service names."""
        return sorted(self.services.keys())

    def get_supported_versions(self, service: Optional[str] = None) -> List[str]:
        """Get all discovered API versions for a service."""
        if service is None:
            service = DEFAULT_SERVICE
        service_versions = self.services.get(service, {})
        return sorted(service_versions.keys(), key=version.parse)

    def get_latest_version(self, service: Optional[str] = None) -> Optional[str]:
        """Get the latest available API version for a service."""
        versions = self.get_supported_versions(service)
        return versions[-1] if versions else None

    def get_modules_for_version(self, api_version: str, service: Optional[str] = None) -> List[str]:
        """Get list of modules available for a specific service and API version."""
        if service is None:
            service = DEFAULT_SERVICE
        return self.services.get(service, {}).get(api_version, [])

    def get_versions_for_module(self, module_name: str) -> List[str]:
        """Get list of API versions that implement a module."""
        return self.module_versions.get(module_name, [])

    def find_best_version(self, requested_version: str, module_name: str) -> Optional[str]:
        """
        Find the best available version for a module.

        Strategy:
        1. Try exact match
        2. Try closest lower version (backward compatible)
        3. Try closest higher version (forward compatible, with warning)
        """
        available = self.get_versions_for_module(module_name)

        if not available:
            logger.error("Module '%s' not found in any API version", module_name)
            return None

        requested = version.parse(requested_version)
        available_parsed = [(v, version.parse(v)) for v in available]

        if requested_version in available:
            return requested_version

        lower_versions = [(v, vp) for v, vp in available_parsed if vp <= requested]

        if lower_versions:
            best = max(lower_versions, key=lambda x: x[1])[0]
            logger.warning("Using version %s for %s (requested %s, closest lower version)", best, module_name, requested_version)
            return best

        higher_versions = [(v, vp) for v, vp in available_parsed if vp > requested]

        if higher_versions:
            best = min(higher_versions, key=lambda x: x[1])[0]
            logger.warning(
                "Using version %s for %s (requested %s, closest higher version - may have compatibility issues)", best, module_name, requested_version
            )
            return best

        return None

    def module_supports_version(self, module_name: str, api_version: str) -> bool:
        """Check if a module has an implementation for an API version."""
        return api_version in self.get_versions_for_module(module_name)
