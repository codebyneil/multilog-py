"""Synchronous Logger class for multilog-py."""

from __future__ import annotations

from typing import Any

from multilog._core import _LoggerCore
from multilog.levels import LogLevel
from multilog.sinks.base import BaseSink


class Logger:
    """
    Synchronous multi-destination logger.

    Wraps _LoggerCore to provide a clean synchronous API for logging
    to multiple sinks simultaneously.

    Example:
        logger = Logger()
        logger.log("User action", LogLevel.INFO, {"user_id": 123})

    Can also be used as a context manager:
        with Logger() as logger:
            logger.log("Starting", LogLevel.INFO)
    """

    def __init__(
        self,
        sinks: list[BaseSink] | None = None,
        default_context: dict[str, Any] | None = None,
    ):
        """
        Initialize logger.

        Args:
            sinks: List of log sinks. If None, creates sinks from env.
            default_context: Context merged into all log entries.
        """
        self._core = _LoggerCore(sinks, default_context)

    def log(
        self,
        message: str,
        level: LogLevel,
        content: dict[str, Any] | None = None,
    ) -> None:
        """
        Send a log entry to all configured sinks.

        Args:
            message: Log message
            level: Log level
            content: Additional metadata to include
        """
        self._core.log(message, level, content)

    def log_endpoint(
        self,
        endpoint_name: str,
        method: str,
        path: str,
        headers: dict[str, str],
        query_params: dict[str, str] | None = None,
        body: Any = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """
        Log an HTTP endpoint invocation with full request details.

        Args:
            endpoint_name: Name/identifier for the endpoint
            method: HTTP method (GET, POST, etc.)
            path: URL path
            headers: Request headers
            query_params: Query string parameters
            body: Request body
            context: Additional context to include
        """
        self._core.log_endpoint(endpoint_name, method, path, headers, query_params, body, context)

    def log_exception(
        self,
        message: str,
        exception: Exception,
        context: dict[str, Any] | None = None,
    ) -> None:
        """
        Log an exception with full stacktrace and error details.

        Args:
            message: Descriptive message about the error
            exception: The exception object
            context: Additional context to include
        """
        self._core.log_exception(message, exception, context)

    def close(self) -> None:
        """Close all sinks that support cleanup."""
        self._core.close()

    def __enter__(self) -> Logger:
        """Enter synchronous context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit synchronous context manager and cleanup."""
        self.close()
