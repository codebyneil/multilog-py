"""File sink for multilog-py."""

import json
from pathlib import Path
from typing import Any

from multilog.levels import LogLevel
from multilog.sinks.base import BaseSink


class FileSink(BaseSink):
    """Sink for logging to a file in JSONL format."""

    def __init__(
        self,
        file_path: str | Path,
        append: bool = True,
        default_context: dict[str, Any] | None = None,
        included_levels: list[LogLevel] | None = None,
    ):
        """
        Initialize file sink.

        Args:
            file_path: Path to the log file
            append: Whether to append to existing file (True) or overwrite (False)
            default_context: Default context merged into all log entries from this sink.
            included_levels: Log levels this sink will emit. Defaults to all levels.
        """
        super().__init__(default_context=default_context, included_levels=included_levels)
        self.file_path = Path(file_path)
        self.mode = "a" if append else "w"

        # Ensure parent directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _emit(self, payload: dict[str, Any]) -> None:
        """
        Write log entry to file as JSON line.

        Args:
            payload: Log payload to write
        """
        with open(self.file_path, mode=self.mode) as f:
            f.write(json.dumps(payload) + "\n")
