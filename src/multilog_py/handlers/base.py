"""Base handler interface for multilog-py."""

import sys
from abc import ABC, abstractmethod
from typing import Any

from multilog_py.levels import LogLevel


class BaseHandler(ABC):
    """Abstract base class for log handlers."""

    def __init__(self, level: LogLevel = LogLevel.DEBUG):
        """
        Initialize the handler.

        Args:
            level: Minimum log level to emit (default: DEBUG)
        """
        self.level = level

    @abstractmethod
    async def emit(self, payload: dict[str, Any]) -> None:
        """
        Send a log entry to the destination.

        Must be implemented by subclasses.

        Args:
            payload: Dictionary containing log data

        Raises:
            HandlerError: If the handler fails to emit the log
        """
        pass

    async def handle(self, payload: dict[str, Any]) -> None:
        """
        Handle a log entry with error handling.

        Filters by level, then calls emit(). Errors are printed to stderr
        but do not raise exceptions (graceful degradation).

        Args:
            payload: Dictionary containing log data
        """
        try:
            log_level = LogLevel(payload.get("level", "info"))
            if self._should_log(log_level):
                await self.emit(payload)
        except Exception as exc:
            # Graceful degradation - log to stderr but don't crash
            print(
                f"Handler {self.__class__.__name__} failed: {exc}",
                file=sys.stderr,
            )

    def _should_log(self, log_level: LogLevel) -> bool:
        """
        Check if this log level should be emitted.

        Args:
            log_level: The log level to check

        Returns:
            True if the log should be emitted, False otherwise
        """
        level_priority = {
            "trace": 0,
            "debug": 1,
            "info": 2,
            "warn": 3,
            "error": 4,
            "fatal": 5,
        }
        return level_priority[log_level.value] >= level_priority[self.level.value]
