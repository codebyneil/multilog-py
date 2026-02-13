"""Utility functions for multilog-py."""

from typing import Any


def serialize_error(error: Exception) -> dict[str, Any]:
    """
    Recursively serialize an exception to a JSON-serializable dict.

    Mirrors the errorToObject function from the TypeScript implementation.

    Args:
        error: Exception to serialize

    Returns:
        Dictionary containing error properties
    """
    if isinstance(error, Exception):
        result: dict[str, Any] = {
            "type": type(error).__name__,
            "message": str(error),
        }

        # Add all error attributes
        for key in dir(error):
            if not key.startswith("_"):
                try:
                    value = getattr(error, key)
                    if not callable(value):
                        result[key] = _serialize_value(value)
                except Exception:
                    # Skip attributes that raise errors
                    pass

        return result

    return {"error": str(error)}


def _serialize_value(value: Any) -> Any:
    """
    Recursively serialize a value to be JSON-compatible.

    Args:
        value: Value to serialize

    Returns:
        JSON-serializable representation of the value
    """
    if isinstance(value, Exception):
        return serialize_error(value)
    elif isinstance(value, (str, int, float, bool, type(None))):
        return value
    elif isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    elif isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    else:
        # Fallback to string representation for non-serializable types
        return str(value)
