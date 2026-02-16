"""Console sink for multilog-py."""

import json
import sys
from datetime import UTC, datetime
from typing import Any

from multilog.levels import LogLevel
from multilog.sinks.base import BaseSink


class ConsoleSink(BaseSink):
    """Sink for logging to console (stdout/stderr)."""

    # ANSI color codes
    COLORS = {
        "trace": "\033[90m",  # Bright black (gray)
        "debug": "\033[36m",  # Cyan
        "info": "\033[32m",  # Green
        "warn": "\033[33m",  # Yellow
        "error": "\033[31m",  # Red
        "fatal": "\033[35m",  # Magenta
        "reset": "\033[0m",  # Reset
    }

    def __init__(
        self,
        use_color: bool = True,
        default_context: dict[str, Any] | None = None,
        included_levels: list[LogLevel] | None = None,
    ):
        """
        Initialize console sink.

        Args:
            use_color: Whether to use ANSI color codes
            default_context: Default context merged into all log entries from this sink.
            included_levels: Log levels this sink will emit. Defaults to all levels.
        """
        super().__init__(default_context=default_context, included_levels=included_levels)
        self.use_color = use_color

    def _emit(self, payload: dict[str, Any]) -> None:
        """
        Print formatted log to stdout or stderr.

        Format: timestamp  LEVEL  message  {context}

        Args:
            payload: Log payload to print
        """
        level = payload.get("level", "info")
        message = payload.get("message", "")
        timestamp_ms = payload.get("timestamp_ms", 0)

        # Convert epoch ms to human-readable timestamp (fixed 23-char width)
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{dt.microsecond // 1000:03d}"

        # Determine output stream (stderr for errors/warnings/fatal, stdout otherwise)
        stream = sys.stderr if level in ("error", "warn", "fatal") else sys.stdout

        # Fixed-width level (5 chars, left-aligned to cover "TRACE"/"FATAL"/"DEBUG"/"ERROR"/"WARN"/"INFO")
        level_str = level.upper().ljust(5)

        # Format the log line
        if self.use_color:
            color = self.COLORS.get(level, "")
            reset = self.COLORS["reset"]
            formatted = f"{timestamp}  {color}{level_str}{reset}  {message}"
        else:
            formatted = f"{timestamp}  {level_str}  {message}"

        # Add context if present
        excluded_keys = ("level", "message", "timestamp_ms")
        context = {k: v for k, v in payload.items() if k not in excluded_keys}
        if context:
            formatted += f"  {json.dumps(context)}"

        print(formatted, file=stream)
