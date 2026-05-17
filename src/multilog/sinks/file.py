"""File sink for multilog-py."""

import json
import threading
from pathlib import Path
from typing import Any

from multilog.exceptions import SinkError
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

        The file handle is opened once and reused for every emit, guarded by
        a lock so concurrent threads (e.g. via AsyncLogger) cannot interleave
        partial JSON lines. The file is opened in line-buffered text mode so
        each entry is flushed to the OS on its trailing newline.

        Args:
            file_path: Path to the log file
            append: Whether to append to existing file (True) or overwrite (False)
            default_context: Default context merged into all log entries from this sink.
            included_levels: Log levels this sink will emit. Defaults to all levels.
        """
        super().__init__(default_context=default_context, included_levels=included_levels)
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        mode = "a" if append else "w"
        self._fh = self.file_path.open(mode=mode, encoding="utf-8", buffering=1)
        self._lock = threading.Lock()
        self._closed = False

    def _emit(self, payload: dict[str, Any]) -> None:
        """
        Write log entry to file as JSON line.

        Args:
            payload: Log payload to write
        """
        line = json.dumps(payload) + "\n"
        with self._lock:
            if self._closed:
                raise SinkError(f"FileSink({self.file_path}) is closed")
            self._fh.write(line)

    def close(self) -> None:
        """Flush and close the underlying file handle. Idempotent."""
        with self._lock:
            if self._closed:
                return
            self._fh.flush()
            self._fh.close()
            self._closed = True
