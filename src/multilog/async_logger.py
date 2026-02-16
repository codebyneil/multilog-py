"""Async wrapper around _LoggerCore for multilog-py."""

import asyncio
from typing import Any

from multilog._core import _LoggerCore
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
        await asyncio.to_thread(self._core.log, message, level, content)

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
        await asyncio.to_thread(
            self._core.log_endpoint,
            endpoint_name,
            method,
            path,
            headers,
            query_params,
            body,
            context,
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
        await asyncio.to_thread(self._core.log_exception, message, exception, context)

    async def close(self) -> None:
        """Close all sinks. Runs in a thread executor."""
        await asyncio.to_thread(self._core.close)

    async def __aenter__(self) -> AsyncLogger:
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager and cleanup."""
        await self.close()
