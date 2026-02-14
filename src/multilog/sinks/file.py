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
        level: LogLevel = LogLevel.DEBUG,
        append: bool = True,
    ):
        """
        Initialize file sink.

        Args:
            file_path: Path to the log file
            level: Minimum log level to emit
            append: Whether to append to existing file (True) or overwrite (False)
        """
        super().__init__(level)
        self.file_path = Path(file_path)
        self.mode = "a" if append else "w"

        # Ensure parent directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, payload: dict[str, Any]) -> None:
        """
        Write log entry to file as JSON line.

        Args:
            payload: Log payload to write
        """
        with open(self.file_path, mode=self.mode) as f:
            f.write(json.dumps(payload) + "\n")
