"""Console handler for multilog-py."""

import json
import sys
from typing import Any

from multilog.handlers.base import BaseHandler
from multilog.levels import LogLevel


class ConsoleHandler(BaseHandler):
    """Handler for logging to console (stdout/stderr)."""

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

    def __init__(self, level: LogLevel = LogLevel.DEBUG, use_color: bool = True):
        """
        Initialize console handler.

        Args:
            level: Minimum log level to emit
            use_color: Whether to use ANSI color codes
        """
        super().__init__(level)
        self.use_color = use_color

    def emit(self, payload: dict[str, Any]) -> None:
        """
        Print formatted log to stdout or stderr.

        Args:
            payload: Log payload to print
        """
        level = payload.get("level", "info")
        message = payload.get("message", "")

        # Determine output stream (stderr for errors/warnings/fatal, stdout otherwise)
        stream = sys.stderr if level in ("error", "warn", "fatal") else sys.stdout

        # Format the log message
        if self.use_color:
            color = self.COLORS.get(level, "")
            reset = self.COLORS["reset"]
            formatted = f"{color}[{level.upper()}]{reset} {message}"
        else:
            formatted = f"[{level.upper()}] {message}"

        # Add context if present
        excluded_keys = ("level", "message", "timestamp_ms")
        context = {k: v for k, v in payload.items() if k not in excluded_keys}
        if context:
            formatted += f" {json.dumps(context)}"

        print(formatted, file=stream)
