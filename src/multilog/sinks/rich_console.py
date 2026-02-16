"""Rich-powered console sink for multilog-py."""

import json
from datetime import UTC, datetime
from typing import Any

from rich.console import Console
from rich.pretty import pretty_repr
from rich.text import Text
from rich.theme import Theme

from multilog.levels import LogLevel
from multilog.sinks.base import BaseSink

# Extend rich's default theme with multilog's trace level.
# All other levels use rich's built-in logging.level.* styles:
#   debug -> green, info -> blue, warning -> yellow,
#   error -> bold red, critical -> bold red reverse
_MULTILOG_THEME = Theme({"logging.level.trace": "dim"})


class RichConsoleSink(BaseSink):
    """Sink for logging to console with rich styling and pretty-printed context.

    Format: ``timestamp  LEVEL     message  {context}``

    Uses rich's built-in theme for level colors and ``pretty_repr`` for
    readable context dictionaries.  Routes warning/error/critical to stderr,
    all others to stdout.
    """

    def __init__(
        self,
        use_color: bool = True,
        pretty_context: bool = True,
        default_context: dict[str, Any] | None = None,
        included_levels: list[LogLevel] | None = None,
    ):
        """
        Initialize rich console sink.

        Args:
            use_color: Whether to use colors and styling. When False, rich still
                formats output but suppresses ANSI codes.
            pretty_context: Whether to pretty-print context dicts using
                ``rich.pretty.pretty_repr``. When False, uses ``json.dumps``.
            default_context: Default context merged into all log entries from this sink.
            included_levels: Log levels this sink will emit. Defaults to all levels.
        """
        super().__init__(default_context=default_context, included_levels=included_levels)
        self.pretty_context = pretty_context

        console_kwargs: dict[str, Any] = {
            "highlight": False,
            "theme": _MULTILOG_THEME,
        }
        if not use_color:
            console_kwargs["no_color"] = True

        self._stdout_console = Console(**console_kwargs)
        self._stderr_console = Console(stderr=True, **console_kwargs)

    def _emit(self, payload: dict[str, Any]) -> None:
        """
        Print a styled log line to the appropriate console.

        Args:
            payload: Log payload to print
        """
        level = payload.get("level", "info")
        message = payload.get("message", "")
        timestamp_ms = payload.get("timestamp_ms", 0)

        # Convert epoch ms to human-readable timestamp (fixed 23-char width)
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{dt.microsecond // 1000:03d}"

        # Pick the right console
        is_error_level = level in ("error", "warning", "critical")
        console = self._stderr_console if is_error_level else self._stdout_console

        # Fixed-width level (8 chars, left-aligned to cover CRITICAL)
        level_str = level.upper().ljust(8)

        # Build styled text — using Text() prevents rich markup injection
        line = Text()
        line.append(timestamp)
        line.append("  ")
        line.append(level_str, style=f"logging.level.{level}")
        line.append("  ")
        line.append(message)

        # Add context if present
        excluded_keys = ("level", "message", "timestamp_ms")
        context = {k: v for k, v in payload.items() if k not in excluded_keys}
        if context:
            line.append("  ")
            if self.pretty_context:
                line.append(pretty_repr(context), style="dim")
            else:
                line.append(json.dumps(context), style="dim")

        console.print(line)
