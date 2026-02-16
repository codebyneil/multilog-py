"""Base sink interface for multilog-py."""

from abc import ABC, abstractmethod
from typing import Any

from multilog.exceptions import ContextError
from multilog.levels import LogLevel


class BaseSink(ABC):
    """Abstract base class for log sinks."""

    def __init__(
        self,
        default_context: dict[str, Any] | None = None,
        included_levels: list[LogLevel] | None = None,
    ):
        """
        Initialize the sink.

        Args:
            default_context: Default context merged into all log entries from this sink.
            included_levels: Log levels this sink will emit. Defaults to all levels.
        """
        self.default_context = default_context or {}
        self.included_levels = included_levels if included_levels is not None else list(LogLevel)

    def emit(self, payload: dict[str, Any]) -> None:
        """
        Merge sink default_context into the payload and delegate to _emit.

        Args:
            payload: Dictionary containing log data
        """
        merged = {**self.default_context, **payload} if self.default_context else payload
        self._emit(merged)

    @abstractmethod
    def _emit(self, payload: dict[str, Any]) -> None:
        """
        Send a log entry to the destination.

        Must be implemented by subclasses.

        Args:
            payload: Dictionary containing log data (with sink context already merged)

        Raises:
            SinkError: If the sink fails to emit the log
        """
        pass

    def _should_log(self, log_level: LogLevel) -> bool:
        """
        Check if this log level should be emitted.

        Args:
            log_level: The log level to check

        Returns:
            True if the log level is in included_levels, False otherwise
        """
        return log_level in self.included_levels

    def update_context(self, **kwargs: Any) -> None:
        """Merge key-value pairs into this sink's default context.

        Existing keys with the same name are overwritten.

        Args:
            **kwargs: Key-value pairs to merge into default_context.
        """
        self.default_context.update(kwargs)

    def remove_context(self, *keys: str) -> None:
        """Remove keys from this sink's default context.

        Args:
            *keys: Names of keys to remove from default_context.

        Raises:
            ContextError: If any key does not exist in the context.
        """
        missing = [k for k in keys if k not in self.default_context]
        if missing:
            raise ContextError(f"Keys not found in context: {', '.join(missing)}")
        for key in keys:
            del self.default_context[key]

    def clear_context(self) -> None:
        """Remove all keys from this sink's default context."""
        self.default_context.clear()
