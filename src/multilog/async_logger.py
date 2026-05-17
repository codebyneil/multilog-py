"""Async wrapper around _LoggerCore for multilog-py."""

from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING, Any

from multilog._core import _LoggerCore
from multilog.levels import LogLevel
from multilog.sinks.base import BaseSink

if TYPE_CHECKING:
    from collections.abc import Callable
    from concurrent.futures import Executor


class AsyncLogger:
    """
    Asynchronous logger that wraps _LoggerCore.

    All logging methods are async and run the synchronous core methods
    in a thread executor (``asyncio.to_thread()`` by default, or a
    user-provided ``concurrent.futures.Executor``) so the event loop is
    not blocked during sink I/O.

    Example:
        async with AsyncLogger() as logger:
            await logger.log("User action", LogLevel.INFO, {"user_id": 123})
    """

    def __init__(
        self,
        sinks: list[BaseSink] | None = None,
        default_context: dict[str, Any] | None = None,
        included_levels: list[LogLevel] | None = None,
        executor: Executor | None = None,
    ):
        """
        Initialize the async logger.

        Args:
            sinks: List of log sinks. If None, creates sinks from env.
            default_context: Context merged into all log entries.
            included_levels: If set, log entries whose level is not in this
                list are dropped before payload construction. Per-sink
                ``included_levels`` filters still apply on top.
            executor: Optional executor to run sink I/O on. When ``None``,
                each call uses ``asyncio.to_thread()`` (the running loop's
                default executor). Pass a ``ThreadPoolExecutor(max_workers=N)``
                to cap concurrent sink I/O.
        """
        self._core = _LoggerCore(sinks, default_context, included_levels)
        self._executor = executor

    async def _run(self, fn: Callable[..., Any], *args: Any) -> Any:
        """Run ``fn(*args)`` on the configured executor."""
        if self._executor is None:
            return await asyncio.to_thread(fn, *args)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, functools.partial(fn, *args))

    async def log(
        self,
        message: str,
        level: LogLevel,
        context: dict[str, Any] | None = None,
    ) -> None:
        """
        Send a log entry to all configured sinks.

        Runs in a thread executor to avoid blocking the event loop.

        Args:
            message: Log message
            level: Log level
            context: Additional metadata to include
        """
        await self._run(self._core.log, message, level, context)

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
        await self._run(
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
        await self._run(self._core.log_exception, message, exception, context)

    async def close(self) -> None:
        """Close all sinks. Runs in a thread executor."""
        await self._run(self._core.close)

    async def __aenter__(self) -> AsyncLogger:
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager and cleanup."""
        await self.close()
