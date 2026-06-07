"""Shared state and dispatch primitives for multilog-py loggers.

A :class:`_LoggerState` holds the mutable, thread-safe state for a single named
logger: its sinks and its base context. The synchronous ``Logger`` and the
``AsyncLogger`` for a given name share one ``_LoggerState`` instance, which is
how ``configure()`` can reconfigure a live logger in place without ever
replacing the handle the caller is holding.

Dispatch is implemented as free functions that operate on a snapshot of the
state, so a log call never holds the state lock while doing sink I/O.
"""

from __future__ import annotations

import sys
import threading
import time
import traceback
from typing import TYPE_CHECKING, Any

from multilog.levels import LogLevel

if TYPE_CHECKING:
    from collections.abc import Iterable

    from multilog.sinks.base import BaseSink


class _LoggerState:
    """Thread-safe mutable state shared by a logger's sync and async views."""

    def __init__(
        self,
        name: str,
        sinks: Iterable[BaseSink] | None = None,
        context: dict[str, Any] | None = None,
    ):
        self.name = name
        self._sinks: tuple[BaseSink, ...] = tuple(sinks) if sinks is not None else ()
        self._context: dict[str, Any] = dict(context) if context else {}
        self._lock = threading.Lock()

    @property
    def sinks(self) -> tuple[BaseSink, ...]:
        """An immutable snapshot of the current sinks, safe to iterate."""
        return self._sinks

    @property
    def context(self) -> dict[str, Any]:
        """The current base context. Treat as read-only; it is replaced, not mutated."""
        return self._context

    def set_context(self, context: dict[str, Any] | None) -> None:
        with self._lock:
            self._context = dict(context) if context else {}

    def set_sinks(self, sinks: Iterable[BaseSink], *, close_removed: bool = True) -> None:
        """Replace the sink set. Sinks no longer present are closed by default.

        The state lock is released before closing removed sinks, so a slow
        ``close()`` (e.g. a batching sink draining its queue) never blocks
        concurrent log dispatch, and an ``on_error`` callback that logs cannot
        deadlock against this mutation.
        """
        new = tuple(sinks)
        with self._lock:
            old = self._sinks
            self._sinks = new
        if close_removed:
            for sink in old:
                if sink not in new:
                    _safe_close(sink)

    def add_sink(self, sink: BaseSink) -> None:
        with self._lock:
            if sink not in self._sinks:
                self._sinks = (*self._sinks, sink)

    def remove_sink(self, sink: BaseSink, *, close: bool = True) -> None:
        with self._lock:
            if sink not in self._sinks:
                return
            self._sinks = tuple(s for s in self._sinks if s is not sink)
        if close:
            _safe_close(sink)

    def close_all(self) -> None:
        with self._lock:
            sinks = self._sinks
        for sink in sinks:
            _safe_close(sink)


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def _build_payload(
    base_context: dict[str, Any],
    bound_context: dict[str, Any],
    message: str,
    level: LogLevel,
    call_context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compose a log payload.

    Context precedence (later wins): base context -> bound context -> per-call
    context. The standard fields (``timestamp_ms``, ``level``, ``message``) are
    written last and therefore cannot be shadowed by user context.
    """
    payload: dict[str, Any] = dict(base_context)
    if bound_context:
        payload.update(bound_context)
    if call_context:
        payload.update(call_context)
    payload["timestamp_ms"] = _now_ms()
    payload["level"] = level
    payload["message"] = message
    return payload


def _dispatch(sinks: tuple[BaseSink, ...], payload: dict[str, Any], level: LogLevel) -> None:
    """Send a payload to every sink that accepts ``level``. Never raises.

    A failure in one sink is isolated and reported to stderr; remaining sinks
    still receive the entry, and the caller of ``log()`` never sees the error.
    """
    for sink in sinks:
        try:
            if sink._accepts(level):
                sink.emit(payload)
        except Exception:
            print(
                f"multilog: sink {type(sink).__name__} failed to emit\n{traceback.format_exc()}",
                file=sys.stderr,
            )


def _exception_context(exception: BaseException) -> dict[str, Any]:
    """Build the context fields describing an exception and its traceback."""
    tb_lines = traceback.format_exception(
        type(exception),
        exception,
        exception.__traceback__,
    )
    return {
        "event_type": "exception",
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "traceback": tb_lines,
    }


def _safe_close(sink: BaseSink) -> None:
    """Close a sink, isolating and reporting any failure. Never raises."""
    try:
        sink.close()
    except Exception:
        print(
            f"multilog: sink {type(sink).__name__} failed to close\n{traceback.format_exc()}",
            file=sys.stderr,
        )
