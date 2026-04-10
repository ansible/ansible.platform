"""Base transformation mixin for bidirectional data transformation.

This module provides the core transformation logic used by all Ansible
and API dataclasses.
"""

import logging
from abc import ABC
from dataclasses import asdict
from typing import Any, Dict, Optional, Type, TypeVar, Union

from .types import TransformContext

logger = logging.getLogger(__name__)
T = TypeVar("T")


class BaseTransformMixin(ABC):
    """
    Base transformation mixin providing bidirectional data transformation.

    All Ansible dataclasses and API dataclasses inherit from this mixin.
    It provides generic transformation logic that works with the specific
    field mappings and transform functions defined in subclasses.

    Attributes:
        _field_mapping: Dict defining field mappings (set by subclasses)
        _transform_registry: Dict of transformation functions (set by subclasses)
    """

    # Subclasses must define these class variables
    _field_mapping: Optional[Dict] = None
    _transform_registry: Optional[Dict] = None

    def to_ansible(self, context: Optional[Union[TransformContext, Dict[str, Any]]] = None) -> Any:
        """
        Transform from API format to Ansible format.

        Args:
            context: Optional TransformContext or dict (same as to_api)

        Returns:
            Ansible dataclass instance
        """
        logger.debug("Transforming %s to Ansible format", self.__class__.__name__)
        ctx = self._normalize_context(context)
        result = self._transform(target_class=self._get_ansible_class(), direction="reverse", context=ctx)
        logger.debug("Transformation to Ansible format completed: %s", result.__class__.__name__)
        return result

    @staticmethod
    def _normalize_context(context: Optional[Union[TransformContext, Dict[str, Any]]]) -> TransformContext:
        """
        Normalize context to TransformContext dataclass.

        Args:
            context: TransformContext or dict

        Returns:
            TransformContext instance
        """
        if context is None:
            raise ValueError("Context is required for transformation")

        if isinstance(context, TransformContext):
            return context

        if isinstance(context, dict):
            # Convert dict to TransformContext for backward compatibility
            return TransformContext(
                manager=context["manager"], session=context["session"], cache=context.get("cache", {}), api_version=context.get("api_version", "1")
            )

        raise TypeError(f"Context must be TransformContext or dict, got {type(context)}")

    def _transform(self, target_class: Type[T], direction: str, context: TransformContext) -> T:
        """
        Generic bidirectional transformation logic.

        Args:
            target_class: Target dataclass type to instantiate
            direction: 'forward' (Ansible->API) or 'reverse' (API->Ansible)
            context: Context dict for transformation functions

        Returns:
            Instance of target_class with transformed data
        """
        logger.debug("Starting %s transformation: %s -> %s", direction, self.__class__.__name__, target_class.__name__)

        # Convert self to dict
        source_data = asdict(self)
        logger.debug("Source data keys: %s", list(source_data.keys()))

        transformed_data = {}

        # Get field mapping from subclass
        mapping = self._field_mapping or {}
        logger.debug("Field mapping contains %s fields", len(mapping))

        # Apply mapping based on direction
        if direction == "forward":
            transformed_data = self._apply_forward_mapping(source_data, mapping, context)
        elif direction == "reverse":
            transformed_data = self._apply_reverse_mapping(source_data, mapping, context)
        else:
            raise ValueError(f"Invalid direction: {direction}")

        logger.debug("Transformed data keys: %s", list(transformed_data.keys()))

        # Allow subclass post-processing hook
        transformed_data = self._post_transform_hook(transformed_data, direction, context)

        # Create and return target class instance
        result = target_class(**transformed_data)
        logger.debug("Created %s instance successfully", target_class.__name__)
        return result

    def _apply_forward_mapping(self, source_data: dict, mapping: dict, context: TransformContext) -> dict:
        """
        Apply forward mapping (Ansible -> API).

        Args:
            source_data: Source data as dict
            mapping: Field mapping configuration
            context: Transform context

        Returns:
            Transformed data dict
        """
        result = {}

        for ansible_field, spec in mapping.items():
            # Get value from source
            value = self._get_nested(source_data, ansible_field)

            if value is None:
                continue

            # Apply forward transformation if specified
            if isinstance(spec, dict) and "forward_transform" in spec:
                transform_name = spec["forward_transform"]
                value = self._apply_transform(value, transform_name, context)

            # Get target field name
            if isinstance(spec, str):
                target_field = spec
            elif isinstance(spec, dict):
                target_field = spec.get("api_field", ansible_field)
            else:
                target_field = ansible_field

            # Set in result
            self._set_nested(result, target_field, value)

        return result

    def _apply_reverse_mapping(self, source_data: dict, mapping: dict, context: TransformContext) -> dict:
        """
        Apply reverse mapping (API -> Ansible).

        Args:
            source_data: Source data as dict
            mapping: Field mapping configuration
            context: Transform context

        Returns:
            Transformed data dict
        """
        result = {}

        for ansible_field, spec in mapping.items():
            # Determine source field name
            if isinstance(spec, str):
                source_field = spec
            elif isinstance(spec, dict):
                source_field = spec.get("api_field", ansible_field)
            else:
                source_field = ansible_field

            # Get value from source
            value = self._get_nested(source_data, source_field)

            if value is None:
                continue

            # Apply reverse transformation if specified
            if isinstance(spec, dict) and "reverse_transform" in spec:
                transform_name = spec["reverse_transform"]
                value = self._apply_transform(value, transform_name, context)

            # Set in result
            self._set_nested(result, ansible_field, value)

        return result

    def _apply_transform(self, value: Any, transform_name: str, context: TransformContext) -> Any:
        """
        Apply a named transformation function.

        Args:
            value: Value to transform
            transform_name: Name of transform function in registry
            context: Transform context

        Returns:
            Transformed value
        """
        if self._transform_registry and transform_name in self._transform_registry:
            logger.debug("Applying transform '%s' to value: %s", transform_name, type(value).__name__)
            transform_func = self._transform_registry[transform_name]
            result = transform_func(value, context)
            logger.debug("Transform '%s' completed: %s", transform_name, type(result).__name__)
            return result
        logger.warning("Transform '%s' not found in registry, returning value unchanged", transform_name)
        return value

    def _get_nested(self, data: dict, path: str) -> Any:
        """
        Get value from nested dict using dot-delimited path.

        Args:
            data: Source dict
            path: Dot-delimited path (e.g., 'user.address.city')

        Returns:
            Value at path, or None if not found
        """
        keys = path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return None
            else:
                return None

        return current

    def _set_nested(self, data: dict, path: str, value: Any) -> None:
        """
        Set value in nested dict using dot-delimited path.

        Args:
            data: Target dict
            path: Dot-delimited path
            value: Value to set
        """
        keys = path.split(".")
        current = data

        # Navigate to parent
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set final value
        current[keys[-1]] = value

    def _post_transform_hook(self, data: dict, direction: str, context: TransformContext) -> dict:
        """
        Hook for module-specific post-processing after transformation.

        Subclasses can override this to add custom logic.

        Args:
            data: Transformed data
            direction: Transform direction
            context: Transform context

        Returns:
            Possibly modified data
        """
        return data

    @classmethod
    def _get_api_class(cls) -> Type:
        """
        Get the API dataclass type for this resource.

        Must be overridden by module-specific mixins.

        Returns:
            API dataclass type

        Raises:
            NotImplementedError: If not overridden
        """
        raise NotImplementedError(f"{cls.__name__} must implement _get_api_class()")

    @classmethod
    def _get_ansible_class(cls) -> Type:
        """
        Get the Ansible dataclass type for this resource.

        Must be overridden by module-specific mixins.

        Returns:
            Ansible dataclass type

        Raises:
            NotImplementedError: If not overridden
        """
        raise NotImplementedError(f"{cls.__name__} must implement _get_ansible_class()")

    def validate(self) -> bool:
        """
        Hook for module-specific validation.

        Subclasses can override to add custom validation logic.

        Returns:
            True if valid, False otherwise
        """
        return True
