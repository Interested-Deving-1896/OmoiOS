"""Null LLM service that returns placeholder responses without making API calls.

This service is used for local development and testing when no API keys are available.
It never makes API calls and never crashes - just returns sensible defaults.
"""

from typing import Optional, TypeVar, get_origin, get_args
from types import UnionType

from pydantic import BaseModel

from omoi_os.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class NullLLMService:
    """LLM service that returns placeholder responses without making API calls.

    Use this for:
    - Local development without API keys
    - Testing workflows that depend on LLM calls
    - CI/CD pipelines where you want deterministic responses
    """

    def __init__(self):
        """Initialize the null LLM service."""
        logger.info("NullLLMService initialized - no API calls will be made")

    async def complete(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> str:
        """Return a placeholder string instead of making an API call.

        Args:
            prompt: User prompt (ignored)
            system_prompt: Optional system prompt (ignored)
            **kwargs: Additional arguments (ignored)

        Returns:
            Placeholder string indicating null mode
        """
        return "[null-mode: no LLM response]"

    async def structured_output(
        self,
        prompt: str,
        output_type: type[T],
        system_prompt: Optional[str] = None,
        output_retries: int = 5,
        http_retries: int = 3,
        **kwargs,
    ) -> T:
        """Return a valid Pydantic model instance with placeholder values.

        Args:
            prompt: User prompt (ignored)
            output_type: Pydantic model class for structured output
            system_prompt: Optional system prompt (ignored)
            output_retries: Number of retries for structured output validation (ignored)
            http_retries: Number of retries for transient HTTP errors (ignored)
            **kwargs: Additional arguments (ignored)

        Returns:
            Instance of output_type with placeholder values
        """
        logger.info(f"NullLLMService: returning placeholder for {output_type.__name__}")
        return self._create_placeholder_instance(output_type)

    def _create_placeholder_instance(self, output_type: type[T]) -> T:
        """Create a placeholder instance of the given Pydantic model.

        Uses model_construct() to create an instance without validation,
        with placeholder values based on field types.

        Args:
            output_type: Pydantic model class

        Returns:
            Instance with placeholder values
        """
        if not issubclass(output_type, BaseModel):
            # For non-Pydantic types, return a sensible default
            return self._get_default_for_type(output_type)

        field_values = {}
        for field_name, field_info in output_type.model_fields.items():
            field_values[field_name] = self._get_placeholder_for_field(
                field_name, field_info
            )

        return output_type.model_construct(**field_values)

    def _get_placeholder_for_field(self, field_name: str, field_info) -> any:
        """Get a placeholder value for a field based on its annotation.

        Args:
            field_name: Name of the field
            field_info: FieldInfo object from Pydantic

        Returns:
            Placeholder value appropriate for the field type
        """
        from pydantic_core import PydanticUndefined

        annotation = field_info.annotation

        # Check if field has a default value (not PydanticUndefined)
        if (
            field_info.default is not PydanticUndefined
            and field_info.default is not None
        ):
            return field_info.default
        if field_info.default_factory is not None:
            return field_info.default_factory()

        return self._get_default_for_type(annotation, field_name)

    def _get_default_for_type(self, annotation: type, field_name: str = "field") -> any:
        """Get a default placeholder value for a given type annotation.

        Args:
            annotation: Type annotation
            field_name: Name of the field (for placeholder strings)

        Returns:
            Placeholder value for the type
        """
        # Handle None
        if annotation is type(None):
            return None

        # Handle Union types (including Optional)
        origin = get_origin(annotation)
        if origin is not None:
            # Handle Optional[T] (Union[T, None])
            if origin is UnionType or (
                hasattr(origin, "__origin__") and origin.__origin__ is UnionType
            ):
                args = get_args(annotation)
                # If one of the args is None, use the other type
                non_none_args = [arg for arg in args if arg is not type(None)]
                if non_none_args:
                    return self._get_default_for_type(non_none_args[0], field_name)
                return None

            # Handle list[T]
            if origin is list:
                return []

            # Handle dict[K, V]
            if origin is dict:
                return {}

            # Handle other generic types
            return None

        # Handle primitive types
        if annotation is str:
            return f"[placeholder: {field_name}]"
        if annotation is int:
            return 0
        if annotation is float:
            return 0.0
        if annotation is bool:
            return False

        # For complex types (nested Pydantic models), recursively create placeholder
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return self._create_placeholder_instance(annotation)

        # Default fallback
        return None
