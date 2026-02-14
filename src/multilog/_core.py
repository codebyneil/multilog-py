"""Shared synchronous core logic for multilog-py loggers."""

import sys
import traceback as tb
from datetime import UTC, datetime
from typing import Any

from multilog.config import Config
from multilog.handlers.base import BaseHandler
from multilog.handlers.betterstack import BetterstackHandler
from multilog.handlers.console import ConsoleHandler
from multilog.levels import LogLevel


class _LoggerCore:
    """
    Pure synchronous core containing shared logging logic.

    Both the synchronous Logger and AsyncLogger delegate to this class
    for payload construction and handler dispatch.
    """

    def __init__(
        self,
        handlers: list[BaseHandler] | None = None,
        default_context: dict[str, Any] | None = None,
    ):
        self.handlers = handlers or self._create_default_handlers()
        self.default_context = default_context or {}

    def _create_default_handlers(self) -> list[BaseHandler]:
        """Create default handlers from environment variables."""
        config = Config.from_env()
        handlers: list[BaseHandler] = []

        # Always include console handler
        handlers.append(ConsoleHandler())

        # Add Betterstack if both token and ingest URL are configured
        if config.betterstack_token and config.betterstack_ingest_url:
            handlers.append(BetterstackHandler.from_config(config))

        return handlers

    def _build_payload(
        self,
        message: str,
        level: LogLevel,
        content: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the log payload dictionary."""
        return {
            "timestamp_ms": int(datetime.now(UTC).timestamp() * 1000),
            "message": message,
            "level": level.value,
            **self.default_context,
            **(content or {}),
        }

    def log(
        self,
        message: str,
        level: LogLevel,
        content: dict[str, Any] | None = None,
    ) -> None:
        """
        Send a log entry to all configured handlers synchronously.

        Args:
            message: Log message
            level: Log level
            content: Additional metadata to include
        """
        payload = self._build_payload(message, level, content)
        self._dispatch(payload)

    def _dispatch(self, payload: dict[str, Any]) -> None:
        """Dispatch payload to all handlers sequentially with error handling."""
        for handler in self.handlers:
            try:
                log_level = LogLevel(payload.get("level", "info"))
                if handler._should_log(log_level):
                    handler.emit(payload)
            except Exception as exc:
                print(
                    f"Handler {handler.__class__.__name__} failed: {exc}",
                    file=sys.stderr,
                )

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
        self.log(
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
        tb_lines = tb.format_exception(
            type(exception),
            exception,
            exception.__traceback__,
        )

        self.log(
            message,
            LogLevel.ERROR,
            {
                "event_type": "exception",
                "exception_type": type(exception).__name__,
                "exception_message": str(exception),
                "traceback": tb_lines,
                **(context or {}),
            },
        )

    def close(self) -> None:
        """Close all handlers that support cleanup."""
        for handler in self.handlers:
            if hasattr(handler, "close") and callable(handler.close):
                try:
                    handler.close()
                except Exception as exc:
                    print(
                        f"Handler {handler.__class__.__name__} close failed: {exc}",
                        file=sys.stderr,
                    )
