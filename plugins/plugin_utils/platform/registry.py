"""API version registry for dynamic version discovery.

This module provides filesystem-based discovery of available API versions
and module implementations without hardcoded version lists.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

# Commented out for production - q library causes worker crashes
# import q

logger = logging.getLogger(__name__)

try:
    from packaging import version
except ImportError:
    # Fallback for environments without packaging
    import re

    class SimpleVersion:
        """Simple version parser for basic version comparison."""

        def __init__(self, version_str: str):
            self.version_str = version_str
            # Extract numeric parts
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


class APIVersionRegistry:
    """
    Registry that discovers and manages API version information.

    Scans the api/ directory to find available versions and tracks
    which modules are implemented for each version.

    Attributes:
        api_base_path: Path to api/ directory containing versioned modules
        ansible_models_path: Path to ansible_models/ with stable interfaces
        versions: Dict mapping version string to available modules
        module_versions: Dict mapping module name to available versions
    """

    def __init__(self, api_base_path: Optional[str] = None, ansible_models_path: Optional[str] = None):
        """
        Initialize registry and discover versions.

        Args:
            api_base_path: Path to api/ directory (auto-detected if None)
            ansible_models_path: Path to ansible_models/ (auto-detected if None)
        """
        # Auto-detect paths if not provided

        if api_base_path is None:
            # Assume we're in plugin_utils/platform/
            current_file = Path(__file__)
            plugin_utils = current_file.parent.parent
            api_base_path = str(plugin_utils / "api")

        if ansible_models_path is None:
            current_file = Path(__file__)
            plugin_utils = current_file.parent.parent
            ansible_models_path = str(plugin_utils / "ansible_models")

        self.api_base_path = Path(api_base_path)
        self.ansible_models_path = Path(ansible_models_path)

        # Storage for discovered information
        self.versions: Dict[str, List[str]] = {}  # version -> [modules]
        self.module_versions: Dict[str, List[str]] = {}  # module -> [versions]

        # Discover on init
        self._discover_versions()

    def _discover_versions(self) -> None:
        """Scan filesystem to discover API versions and modules."""
        if not self.api_base_path.exists():
            logger.warning("API base path not found: %s", self.api_base_path)
            return

        # Scan api/ directory for version directories (v1/, v2/, etc.)
        for version_dir in self.api_base_path.iterdir():
            if not version_dir.is_dir():
                continue

            # Must start with 'v' and contain digits
            if not version_dir.name.startswith("v"):
                continue

            # Extract version string: v1 -> 1, v2_1 -> 2.1
            version_str = version_dir.name[1:].replace("_", ".")

            # Find module implementations in this version
            module_files = [f for f in version_dir.glob("*.py") if not f.name.startswith("_") and f.name != "generated"]

            module_names = [f.stem for f in module_files]

            # Store version info
            self.versions[version_str] = module_names

            # Update module -> versions mapping
            for module_name in module_names:
                if module_name not in self.module_versions:
                    self.module_versions[module_name] = []
                self.module_versions[module_name].append(version_str)

        # Sort version lists
        for module_name in self.module_versions:
            self.module_versions[module_name].sort(key=version.parse)

        logger.info("Discovered %s API versions: %s", len(self.versions), sorted(self.versions.keys(), key=version.parse))

    def get_supported_versions(self) -> List[str]:
        """
        Get all discovered API versions, sorted.

        Returns:
            List of version strings (e.g., ['1', '2', '2.1'])
        """
        return sorted(self.versions.keys(), key=version.parse)

    def get_latest_version(self) -> Optional[str]:
        """
        Get the latest available API version.

        Returns:
            Latest version string, or None if no versions found
        """
        versions = self.get_supported_versions()
        return versions[-1] if versions else None

    def get_modules_for_version(self, api_version: str) -> List[str]:
        """
        Get list of modules available for a specific API version.

        Args:
            api_version: Version string (e.g., '1', '2.1')

        Returns:
            List of module names
        """
        return self.versions.get(api_version, [])

    def get_versions_for_module(self, module_name: str) -> List[str]:
        """
        Get list of API versions that implement a module.

        Args:
            module_name: Module name (e.g., 'user', 'organization')

        Returns:
            List of version strings
        """
        return self.module_versions.get(module_name, [])

    def find_best_version(self, requested_version: str, module_name: str) -> Optional[str]:
        """
        Find the best available version for a module.

        Strategy:
        1. Try exact match
        2. Try closest lower version (backward compatible)
        3. Try closest higher version (forward compatible, with warning)

        Args:
            requested_version: Desired API version
            module_name: Module name

        Returns:
            Best matching version string, or None if not found
        """
        available = self.get_versions_for_module(module_name)

        if not available:
            logger.error("Module '%s' not found in any API version", module_name)
            return None

        requested = version.parse(requested_version)
        available_parsed = [(v, version.parse(v)) for v in available]

        # Exact match
        if requested_version in available:
            return requested_version

        # Find closest lower version (prefer backward compatibility)
        lower_versions = [(v, vp) for v, vp in available_parsed if vp <= requested]

        if lower_versions:
            best = max(lower_versions, key=lambda x: x[1])[0]
            logger.warning("Using version %s for %s (requested %s, closest lower version)", best, module_name, requested_version)
            return best

        # Fallback: closest higher version
        higher_versions = [(v, vp) for v, vp in available_parsed if vp > requested]

        if higher_versions:
            best = min(higher_versions, key=lambda x: x[1])[0]
            logger.warning(
                "Using version %s for %s (requested %s, closest higher version - may have compatibility issues)", best, module_name, requested_version
            )
            return best

        return None

    def module_supports_version(self, module_name: str, api_version: str) -> bool:
        """
        Check if a module has an implementation for an API version.

        Args:
            module_name: Module name
            api_version: Version string

        Returns:
            True if module exists for version
        """
        return api_version in self.get_versions_for_module(module_name)
