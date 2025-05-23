"""
Pydantic integration helpers for FastAirport.
"""

import inspect
import json
from typing import Any, Dict, Type, Union

from pydantic import BaseModel, ValidationError

from .errors import InvalidArgument


def parse_and_validate_params(
    raw_params: Dict[str, Any], func_signature: inspect.Signature
) -> Dict[str, Any]:
    """
    Parses raw parameters, validates them against Pydantic models if specified
    in type hints, and converts to simple types otherwise.
    """
    validated_params: Dict[str, Any] = {}

    for name, param_spec in func_signature.parameters.items():
        # Import Context here to avoid circular imports
        from .context import Context

        if name == "ctx" or (
            param_spec.annotation is not inspect.Parameter.empty
            and param_spec.annotation is Context
        ):
            continue

        raw_value = raw_params.get(name)
        annotation = param_spec.annotation

        # Check if this is a Pydantic model first
        is_pydantic_model = (
            annotation is not inspect.Parameter.empty
            and isinstance(annotation, type)
            and issubclass(annotation, BaseModel)
        )

        if is_pydantic_model:
            try:
                # For Pydantic models, use all raw_params as input
                validated_params[name] = annotation.model_validate(raw_params)
            except ValidationError as e:
                raise InvalidArgument(
                    f"Invalid data for parameter '{name}': {e.errors(include_input=False, include_url=False)}"
                )
            continue

        if raw_value is None:
            if param_spec.default is not inspect.Parameter.empty:
                validated_params[name] = param_spec.default
                continue
            # Check if it's an Optional type hint

            is_optional = (
                hasattr(annotation, "__origin__")
                and annotation.__origin__ is Union
                and type(None) in getattr(annotation, "__args__", ())
            )

            if (
                is_optional
                or annotation is Any
                or annotation is inspect.Parameter.empty
            ):  # Allow None for Optional, Any, or untyped
                validated_params[name] = None
                continue
            else:
                raise InvalidArgument(f"Missing required parameter: '{name}'")

        if annotation is not inspect.Parameter.empty:
            try:
                validated_params[name] = _convert_simple_param(raw_value, annotation)
            except (TypeError, ValueError) as e:
                raise InvalidArgument(
                    f"Invalid value for parameter '{name}': Cannot convert '{raw_value}' to {getattr(annotation, '__name__', str(annotation))}. Error: {e}"
                )
        else:  # No type hint, pass as is
            validated_params[name] = raw_value
    return validated_params


def _convert_simple_param(value: Any, target_type: Type) -> Any:
    """Converts a value to a simple target type if possible."""

    # Handle Optional[T] by unwrapping T
    origin = getattr(target_type, "__origin__", None)
    args = getattr(target_type, "__args__", ())

    if origin is Union and type(None) in args:  # Checks for Optional[T]
        if value is None:
            return None
        # Try to convert to the non-None type in Optional[T]
        actual_type = next(t for t in args if t is not type(None))
        return _convert_simple_param(
            value, actual_type
        )  # Recursive call for the actual type

    if (
        value is None
    ):  # If not Optional and value is None, this is usually an error unless target_type is Any
        if target_type is Any:
            return None
        raise TypeError(
            f"Cannot convert None to non-Optional type {getattr(target_type, '__name__', str(target_type))}"
        )

    # Handle boolean conversion
    if target_type is bool:
        if isinstance(value, str):
            lower_val = value.lower()
            if lower_val in ("false", "0", "no", "off", ""):
                return False
            elif lower_val in ("true", "1", "yes", "on"):
                return True
            else:
                raise ValueError(f"Cannot convert '{value}' to boolean")
        return bool(value)

    if origin is list or target_type is list:
        if not isinstance(value, list):
            if isinstance(value, str):  # try to parse JSON list string
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass  # Fall through if not JSON
            if not isinstance(value, list):  # check again after potential parse
                raise ValueError(
                    f"Expected a list or JSON list string for type {target_type}, got {type(value)}"
                )
        return value
    if origin is dict or target_type is dict:
        if not isinstance(value, dict):
            if isinstance(value, str):  # try to parse JSON dict string
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            if not isinstance(value, dict):
                raise ValueError(
                    f"Expected a dict or JSON dict string for type {target_type}, got {type(value)}"
                )
        return value

    # Standard type conversions
    if target_type is int:
        return int(value)
    if target_type is float:
        return float(value)
    if target_type is str:
        return str(value)

    # If target_type is Any, return value as is
    if target_type is Any:
        return value

    # If no specific conversion and type doesn't match, raise error
    if not isinstance(value, target_type):
        raise TypeError(
            f"Value '{value}' of type {type(value)} is not an instance of expected type {getattr(target_type, '__name__', str(target_type))}"
        )

    return value
