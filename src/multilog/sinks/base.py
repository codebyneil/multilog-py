"""Base sink interface for multilog-py."""

from abc import ABC, abstractmethod
from typing import Any

from multilog.levels import LogLevel


class BaseSink(ABC):
    """Abstract base class for log sinks."""

    def __init__(self, level: LogLevel = LogLevel.DEBUG):
        """
        Initialize the sink.

        Args:
            level: Minimum log level to emit (default: DEBUG)
        """
        self.level = level

    @abstractmethod
    def emit(self, payload: dict[str, Any]) -> None:
        """
        Send a log entry to the destination.

        Must be implemented by subclasses.

        Args:
            payload: Dictionary containing log data

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
            True if the log should be emitted, False otherwise
        """
        return log_level >= self.level
