"""Base sink interface for multilog-py."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from multilog.levels import LogLevel


class BaseSink(ABC):
    """Abstract base class for log sinks.

    Filtering is threshold-based: a sink emits every entry whose level is at
    least ``min_level``. The optional ``only`` set is an escape hatch for the
    rare case where you want an explicit allow-list instead of a threshold —
    when ``only`` is provided it is authoritative and ``min_level`` is ignored.
    """

    def __init__(
        self,
        *,
        min_level: LogLevel = LogLevel.TRACE,
        only: Iterable[LogLevel] | None = None,
    ):
        """Initialize the sink.

        Args:
            min_level: Emit entries at this severity or higher. Defaults to
                ``TRACE`` (emit everything).
            only: If given, an explicit set of levels to emit. Overrides
                ``min_level`` entirely.
        """
        self.min_level = min_level
        self.only: frozenset[LogLevel] | None = frozenset(only) if only is not None else None

    def emit(self, payload: dict[str, Any]) -> None:
        """Send a log entry to the destination.

        The default implementation delegates straight to :meth:`_emit`; the
        dispatcher has already filtered by level. Treat ``payload`` as
        read-only — it is shared across all sinks for a single log call.

        Args:
            payload: Dictionary containing log data.
        """
        self._emit(payload)

    @abstractmethod
    def _emit(self, payload: dict[str, Any]) -> None:
        """Send a log entry to the destination.

        Must be implemented by subclasses. Runs synchronously, possibly on a
        worker thread (``AsyncLogger`` dispatches via a thread).

        Args:
            payload: Dictionary containing log data.

        Raises:
            SinkError: If the sink fails to emit the log. The dispatcher
                isolates and reports failures; an exception here never reaches
                the caller of ``log()``.
        """

    def close(self) -> None:  # noqa: B027 - intentional optional override, not abstract
        """Release sink resources. Subclasses can override if needed."""

    def flush(self, timeout: float | None = None) -> bool:  # noqa: ARG002
        """Block until buffered events are delivered.

        Returns ``True`` once delivered or if there is nothing buffered, ``False``
        on timeout. The default is a no-op (most sinks write synchronously);
        buffering sinks override it.
        """
        return True

    def _accepts(self, level: LogLevel) -> bool:
        """Return whether this sink should emit an entry at ``level``."""
        if self.only is not None:
            return level in self.only
        return level >= self.min_level
