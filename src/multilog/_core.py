"""Shared synchronous core logic for multilog-py loggers."""

import os
import sys
import traceback as tb
from datetime import UTC, datetime
from types import FrameType
from typing import Any

from multilog.exceptions import ConfigError, ContextError
from multilog.levels import LogLevel
from multilog.sinks.base import BaseSink
from multilog.sinks.betterstack import BetterstackSink
from multilog.sinks.console import ConsoleSink


class _LoggerCore:
    """
    Pure synchronous core containing shared logging logic.

    Both the synchronous Logger and AsyncLogger delegate to this class
    for payload construction and sink dispatch.
    """

    def __init__(
        self,
        sinks: list[BaseSink] | None = None,
        default_context: dict[str, Any] | None = None,
    ):
        self.sinks = sinks if sinks is not None else _default_sinks()
        self.default_context = default_context or {}

    def _build_payload(
        self,
        message: str,
        level: LogLevel,
        content: dict[str, Any] | None = None,
        caller_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the log payload dictionary."""
        return {
            "timestamp_ms": int(datetime.now(UTC).timestamp() * 1000),
            "message": message,
            "level": level.value,
            **self.default_context,
            **(caller_info or {}),
            **(content or {}),
        }

    def log(
        self,
        message: str,
        level: LogLevel,
        content: dict[str, Any] | None = None,
        caller_info: dict[str, Any] | None = None,
    ) -> None:
        """
        Send a log entry to all configured sinks synchronously.

        Args:
            message: Log message
            level: Log level
            content: Additional metadata to include
            caller_info: Caller location metadata (file, line, function)
        """
        payload = self._build_payload(message, level, content, caller_info)
        self._dispatch(payload)

    def _dispatch(self, payload: dict[str, Any]) -> None:
        """Dispatch payload to all sinks sequentially with error handling."""
        for sink in self.sinks:
            try:
                log_level = LogLevel(payload.get("level", "info"))
                if sink._should_log(log_level):
                    sink.emit(payload)
            except Exception as exc:
                print(
                    f"Sink {sink.__class__.__name__} failed: {exc}",
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
        caller_info: dict[str, Any] | None = None,
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
            caller_info: Caller location metadata (file, line, function)
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
            caller_info=caller_info,
        )

    def log_exception(
        self,
        message: str,
        exception: Exception,
        context: dict[str, Any] | None = None,
        caller_info: dict[str, Any] | None = None,
    ) -> None:
        """
        Log an exception with full stacktrace and error details.

        Args:
            message: Descriptive message about the error
            exception: The exception object
            context: Additional context to include
            caller_info: Caller location metadata (file, line, function)
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
            caller_info=caller_info,
        )

    def close(self) -> None:
        """Close all sinks that support cleanup."""
        for sink in self.sinks:
            if hasattr(sink, "close") and callable(sink.close):
                try:
                    sink.close()
                except Exception as exc:
                    print(
                        f"Sink {sink.__class__.__name__} close failed: {exc}",
                        file=sys.stderr,
                    )

    def update_context(self, **kwargs: Any) -> None:
        """Merge key-value pairs into the logger's default context.

        Existing keys with the same name are overwritten.

        Args:
            **kwargs: Key-value pairs to merge into default_context.
        """
        self.default_context.update(kwargs)

    def remove_context(self, *keys: str) -> None:
        """Remove keys from the logger's default context.

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
        """Remove all keys from the logger's default context."""
        self.default_context.clear()


def _caller_info(frame: FrameType) -> dict[str, Any]:
    """Extract caller location metadata from a stack frame."""
    return {
        "caller_file": frame.f_code.co_filename,
        "caller_line": frame.f_lineno,
        "caller_function": frame.f_code.co_name,
    }


def _default_sinks() -> list[BaseSink]:
    """Create default sinks from environment variables."""
    sinks: list[BaseSink] = []

    try:
        from multilog.sinks.rich_console import RichConsoleSink

        sinks.append(RichConsoleSink())
    except ImportError:
        sinks.append(ConsoleSink())

    token = os.getenv("BETTERSTACK_TOKEN")
    ingest_url = os.getenv("BETTERSTACK_INGEST_URL")

    if token or ingest_url:
        if not token:
            raise ConfigError(
                "BETTERSTACK_INGEST_URL is set but BETTERSTACK_TOKEN is missing"
            )
        if not ingest_url:
            raise ConfigError(
                "BETTERSTACK_TOKEN is set but BETTERSTACK_INGEST_URL is missing"
            )
        sinks.append(BetterstackSink(token=token, ingest_url=ingest_url))

    return sinks
