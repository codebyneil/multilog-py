"""Console sink for multilog-py."""

import json
import sys
from datetime import UTC, datetime
from typing import Any

from multilog.levels import LogLevel
from multilog.sinks.base import BaseSink


class ConsoleSink(BaseSink):
    """Sink for logging to console (stdout/stderr) as plain text.

    Format: ``timestamp  LEVEL     message  {context}``

    Routes warning/error/critical to stderr, all others to stdout.
    For colored and styled output, use :class:`RichConsoleSink` instead.
    """

    def __init__(
        self,
        default_context: dict[str, Any] | None = None,
        included_levels: list[LogLevel] | None = None,
    ):
        """
        Initialize console sink.

        Args:
            default_context: Default context merged into all log entries from this sink.
            included_levels: Log levels this sink will emit. Defaults to all levels.
        """
        super().__init__(default_context=default_context, included_levels=included_levels)

    def _emit(self, payload: dict[str, Any]) -> None:
        """
        Print formatted log to stdout or stderr.

        Format: timestamp  LEVEL     message  {context}

        Args:
            payload: Log payload to print
        """
        level = payload.get("level", "info")
        message = payload.get("message", "")
        timestamp_ms = payload.get("timestamp_ms", 0)

        # Convert epoch ms to human-readable timestamp (fixed 23-char width)
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{dt.microsecond // 1000:03d}"

        # Determine output stream (stderr for errors/warnings/critical, stdout otherwise)
        stream = sys.stderr if level in ("error", "warning", "critical") else sys.stdout

        # Fixed-width level (8 chars, left-aligned to cover CRITICAL)
        level_str = level.upper().ljust(8)

        formatted = f"{timestamp}  {level_str}  {message}"

        # Add context if present
        excluded_keys = ("level", "message", "timestamp_ms")
        context = {k: v for k, v in payload.items() if k not in excluded_keys}
        if context:
            formatted += f"  {json.dumps(context)}"

        print(formatted, file=stream)
