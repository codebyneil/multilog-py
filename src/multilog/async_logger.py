"""Async wrapper around _LoggerCore for multilog-py."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from multilog._core import _LoggerCore, _caller_info
from multilog.levels import LogLevel
from multilog.sinks.base import BaseSink


class AsyncLogger:
    """
    Asynchronous logger that wraps _LoggerCore.

    All logging methods are async and run the synchronous core methods
    in a thread executor via asyncio.to_thread(), keeping the event loop
    unblocked during sink I/O (file writes, HTTP requests, etc.).

    Example:
        async with AsyncLogger() as logger:
            await logger.log("User action", LogLevel.INFO, {"user_id": 123})
    """

    def __init__(
        self,
        sinks: list[BaseSink] | None = None,
        default_context: dict[str, Any] | None = None,
    ):
        """
        Initialize the async logger.

        Args:
            sinks: List of log sinks. If None, creates sinks from env.
            default_context: Context merged into all log entries.
        """
        self._core = _LoggerCore(sinks, default_context)

    async def log(
        self,
        message: str,
        level: LogLevel,
        content: dict[str, Any] | None = None,
    ) -> None:
        """
        Send a log entry to all configured sinks.

        Runs in a thread executor to avoid blocking the event loop.

        Args:
            message: Log message
            level: Log level
            content: Additional metadata to include
        """
        frame = sys._getframe(1)
        await asyncio.to_thread(self._core.log, message, level, content, _caller_info(frame))

    async def log_endpoint(
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

        Runs in a thread executor to avoid blocking the event loop.

        Args:
            endpoint_name: Name/identifier for the endpoint
            method: HTTP method (GET, POST, etc.)
            path: URL path
            headers: Request headers
            query_params: Query string parameters
            body: Request body
            context: Additional context to include
        """
        frame = sys._getframe(1)
        await asyncio.to_thread(
            self._core.log_endpoint,
            endpoint_name,
            method,
            path,
            headers,
            query_params,
            body,
            context,
            _caller_info(frame),
        )

    async def log_exception(
        self,
        message: str,
        exception: Exception,
        context: dict[str, Any] | None = None,
    ) -> None:
        """
        Log an exception with full stacktrace and error details.

        Runs in a thread executor to avoid blocking the event loop.

        Args:
            message: Descriptive message about the error
            exception: The exception object
            context: Additional context to include
        """
        frame = sys._getframe(1)
        await asyncio.to_thread(self._core.log_exception, message, exception, context, _caller_info(frame))

    async def close(self) -> None:
        """Close all sinks. Runs in a thread executor."""
        await asyncio.to_thread(self._core.close)

    def update_context(self, **kwargs: Any) -> None:
        """Merge key-value pairs into the logger's default context.

        Existing keys with the same name are overwritten.

        Args:
            **kwargs: Key-value pairs to merge into default_context.
        """
        self._core.update_context(**kwargs)

    def remove_context(self, *keys: str) -> None:
        """Remove keys from the logger's default context.

        Args:
            *keys: Names of keys to remove from default_context.

        Raises:
            ContextError: If any key does not exist in the context.
        """
        self._core.remove_context(*keys)

    def clear_context(self) -> None:
        """Remove all keys from the logger's default context."""
        self._core.clear_context()

    async def __aenter__(self) -> AsyncLogger:
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager and cleanup."""
        await self.close()
