"""Main Logger class for multilog-py."""

import asyncio
import traceback as tb
from datetime import UTC, datetime
from typing import Any

from multilog_py.config import Config
from multilog_py.handlers.base import BaseHandler
from multilog_py.handlers.betterstack import BetterstackHandler
from multilog_py.handlers.console import ConsoleHandler
from multilog_py.levels import LogLevel
from multilog_py.utils import serialize_error


class Logger:
    """
    Multi-destination logger supporting multiple handlers.

    Example:
        logger = Logger()
        await logger.log("User action", LogLevel.INFO, {"user_id": 123})
    """

    def __init__(
        self,
        handlers: list[BaseHandler] | None = None,
        default_context: dict[str, Any] | None = None,
    ):
        """
        Initialize logger.

        Args:
            handlers: List of log handlers. If None, creates handlers from env.
            default_context: Context merged into all log entries.
        """
        self.handlers = handlers or self._create_default_handlers()
        self.default_context = default_context or {}

    def _create_default_handlers(self) -> list[BaseHandler]:
        """
        Create default handlers from environment variables.

        Returns:
            List of handlers (Betterstack if configured, otherwise Console)
        """
        config = Config.from_env()
        handlers: list[BaseHandler] = []

        if config.betterstack_token:
            handlers.append(BetterstackHandler.from_config(config))
        else:
            # Fallback to console if no Betterstack config
            handlers.append(ConsoleHandler())

        return handlers

    async def log(
        self,
        message: str,
        level: LogLevel,
        content: dict[str, Any] | None = None,
    ) -> None:
        """
        Send a log entry to all configured handlers.

        Args:
            message: Log message
            level: Log level
            content: Additional metadata to include
        """
        payload = {
            "timestamp_ms": int(datetime.now(UTC).timestamp() * 1000),
            "message": message,
            "level": level.value,
            **self.default_context,
            **(content or {}),
        }

        # Dispatch to all handlers concurrently
        await asyncio.gather(
            *[handler.handle(payload) for handler in self.handlers],
            return_exceptions=True,  # Don't let one handler failure stop others
        )

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

        Args:
            endpoint_name: Name/identifier for the endpoint
            method: HTTP method (GET, POST, etc.)
            path: URL path
            headers: Request headers
            query_params: Query string parameters
            body: Request body (will be JSON serialized if possible)
            context: Additional context to include
        """
        await self.log(
            f"Endpoint Invoked: {endpoint_name}",
            LogLevel.INFO,
            {
                "event_source": "http_endpoint",
                "event_type": "endpoint_invocation",
                "endpoint_name": endpoint_name,
                "request": {
                    "method": method,
                    "path": path,
                    "query": query_params or {},
                    "headers": headers,
                    "body": body,
                },
                **(context or {}),
            },
        )

    async def log_exception(
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
        # Extract traceback
        tb_lines = tb.format_exception(
            type(exception),
            exception,
            exception.__traceback__,
        )

        await self.log(
            message,
            LogLevel.ERROR,
            {
                "event_type": "exception",
                "exception_type": type(exception).__name__,
                "exception_message": str(exception),
                "traceback": tb_lines,
                "error_object": serialize_error(exception),
                **(context or {}),
            },
        )

    async def close(self) -> None:
        """Close all handlers that support cleanup."""
        for handler in self.handlers:
            if hasattr(handler, "close") and callable(getattr(handler, "close")):
                await handler.close()  # type: ignore[misc]

    async def __aenter__(self) -> Logger:
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager and cleanup."""
        await self.close()
