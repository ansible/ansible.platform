"""Dynamic class loader for version-specific implementations.

This module loads Ansible and API dataclasses based on the detected
API version without hardcoded imports.
"""

import importlib
import inspect
import logging
from typing import Dict, Optional, Tuple, Type

from .base_transform import BaseTransformMixin
from .registry import APIVersionRegistry

logger = logging.getLogger(__name__)


def _to_pascal_case(name: str) -> str:
    """Convert a snake_case name to PascalCase (e.g. 'service_type' -> 'ServiceType')."""
    return "".join(part.capitalize() for part in name.split("_"))


class DynamicClassLoader:
    """
    Dynamically load version-specific classes at runtime.

    Loads the appropriate Ansible dataclass and API dataclass/mixin
    based on the module name and API version.

    Attributes:
        registry: APIVersionRegistry for version discovery
        class_cache: Cache of loaded classes to avoid repeated imports
    """

    def __init__(self, registry: APIVersionRegistry):
        """
        Initialize loader with a version registry.

        Args:
            registry: Version registry for discovering available versions
        """
        self.registry = registry
        self._class_cache: Dict[str, Tuple[Type, Type, Type]] = {}

    def load_classes_for_module(self, module_name: str, api_version: str) -> Tuple[Type, Type, Type]:
        """
        Load classes for a module and API version.

        Args:
            module_name: Module name (e.g., 'user', 'organization')
            api_version: API version (e.g., '1', '2.1')

        Returns:
            Tuple of (AnsibleClass, APIClass, MixinClass)

        Raises:
            ValueError: If classes cannot be loaded
        """
        # Find best matching version
        best_version = self.registry.find_best_version(api_version, module_name)

        if not best_version:
            raise ValueError(f"No compatible API version found for module '{module_name}' with requested version '{api_version}'")

        # Check cache
        cache_key = f"{module_name}_{best_version.replace('.', '_')}"
        if cache_key in self._class_cache:
            logger.debug("Using cached classes for %s", cache_key)
            return self._class_cache[cache_key]

        # Load classes
        logger.debug("Loading classes for %s (API version %s)", module_name, best_version)
        ansible_class = self._load_ansible_class(module_name)
        api_class, mixin_class = self._load_api_classes(module_name, best_version)

        # Cache and return
        result = (ansible_class, api_class, mixin_class)
        logger.debug("Loaded classes: %s, %s, %s", ansible_class.__name__, api_class.__name__, mixin_class.__name__)

        return result

    def _load_ansible_class(self, module_name: str) -> Type:
        """
        Load stable Ansible dataclass.

        Args:
            module_name: Module name

        Returns:
            Ansible dataclass type

        Raises:
            ImportError: If module cannot be imported
            ValueError: If class cannot be found
        """
        # Import from ansible_models/<module_name>.py
        module_path = f"ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.{module_name}"

        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            logger.error("Failed to import Ansible module %s: %s", module_path, e)
            raise ImportError(f"Failed to import Ansible module {module_path}: {e}") from e

        # Find Ansible dataclass (e.g., AnsibleUser, AnsibleCACertificate)
        class_name = f"Ansible{_to_pascal_case(module_name)}"
        target_lower = class_name.lower()

        if hasattr(module, class_name):
            return getattr(module, class_name)

        # Case-insensitive fallback (handles acronyms like CA vs Ca)
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if name.lower() == target_lower:
                return obj

        # Last resort: any class starting with 'Ansible'
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if name.startswith("Ansible"):
                return obj

        raise ValueError(f"No Ansible dataclass found in {module_path} (expected {class_name})")

    def _load_api_classes(self, module_name: str, api_version: str) -> Tuple[Type, Type]:
        """
        Load API dataclass and transform mixin for a version.

        Args:
            module_name: Module name
            api_version: API version

        Returns:
            Tuple of (APIClass, MixinClass)

        Raises:
            ImportError: If module cannot be imported
            ValueError: If classes cannot be found
        """
        # Import from api/v<version>/<module_name>.py
        version_normalized = api_version.replace(".", "_")
        module_path = f"ansible_collections.ansible.platform.plugins.plugin_utils.api.v{version_normalized}.{module_name}"

        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            logger.error("Failed to import API module %s: %s", module_path, e)
            raise ImportError(f"Failed to import API module {module_path}: {e}") from e

        # Find API dataclass (e.g., APIUser_v1)
        pascal = _to_pascal_case(module_name)
        api_class_name = f"API{pascal}_v{version_normalized}"
        api_class = self._find_class_in_module(module, [api_class_name, f"API{pascal}", "API*"], f"API dataclass for {module_name}")

        # Find transform mixin (e.g., UserTransformMixin_v1)
        mixin_class_name = f"{pascal}TransformMixin_v{version_normalized}"
        mixin_class = self._find_class_in_module(
            module, [mixin_class_name, f"{pascal}TransformMixin", "*TransformMixin"], f"Transform mixin for {module_name}", base_class=BaseTransformMixin
        )

        return api_class, mixin_class

    def _find_class_in_module(self, module, patterns: list, description: str, base_class: Optional[Type] = None) -> Type:
        """
        Find a class in a module matching patterns.

        Uses case-insensitive matching so class names with acronyms
        (e.g. CACertificate vs CaCertificate) are found regardless
        of capitalisation style.

        Args:
            module: Imported module
            patterns: List of patterns to try (wildcards supported)
            description: Description for error messages
            base_class: Optional base class to filter by

        Returns:
            Matched class type

        Raises:
            ValueError: If no matching class found
        """
        classes = inspect.getmembers(module, inspect.isclass)

        if base_class:
            classes = [(name, cls) for name, cls in classes if issubclass(cls, base_class) and cls != base_class]

        for pattern in patterns:
            if "*" in pattern:
                prefix, _sep, suffix = pattern.partition("*")
                p_lower, s_lower = prefix.lower(), suffix.lower()
                for name, cls in classes:
                    n_lower = name.lower()
                    if n_lower.startswith(p_lower) and n_lower.endswith(s_lower):
                        return cls
            else:
                pat_lower = pattern.lower()
                for name, cls in classes:
                    if name.lower() == pat_lower:
                        return cls

        raise ValueError("No %s found in %s. Tried patterns: %s" % (description, module.__name__, patterns))
