"""Synchronous Logger for multilog-py."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from multilog._core import (
    _build_payload,
    _dispatch,
    _exception_context,
    _LoggerState,
)
from multilog.levels import LogLevel

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from multilog.sinks.base import BaseSink


class Logger:
    """Synchronous multi-destination logger.

    The blessed way to obtain a ``Logger`` is :func:`multilog.get_logger`, which
    returns a process-stable handle whose sinks and context can be reconfigured
    in place via :func:`multilog.configure`. Constructing ``Logger`` directly
    creates a standalone logger with its own state that the registry does not
    manage — handy for tests and ad-hoc use.

    Example::

        from multilog import get_logger, configure, ConsoleSink, LogLevel

        configure(sinks=[ConsoleSink()])
        log = get_logger()
        log.log("User action", LogLevel.INFO, {"user_id": 123})
    """

    def __init__(
        self,
        sinks: Iterable[BaseSink] | None = None,
        context: dict[str, Any] | None = None,
        *,
        name: str = "app",
    ):
        """Create a standalone logger with its own state.

        Args:
            sinks: Sinks to dispatch to.
            context: Base context merged into every entry.
            name: Identifying name (does not register the logger).
        """
        self._state = _LoggerState(name, sinks, context)
        self._bound_context: dict[str, Any] = {}
        self._is_bound = False

    @classmethod
    def _from_state(
        cls,
        state: _LoggerState,
        bound_context: dict[str, Any] | None = None,
        *,
        is_bound: bool = False,
    ) -> Logger:
        obj = cls.__new__(cls)
        obj._state = state
        obj._bound_context = dict(bound_context) if bound_context else {}
        obj._is_bound = is_bound
        return obj

    @property
    def name(self) -> str:
        return self._state.name

    @property
    def context(self) -> Mapping[str, Any]:
        """Read-only view of the context attached to every entry from this logger.

        Merges the shared base context with this view's bound context. Useful
        for extending context via ``configure``::

            configure(context={**logger.context, "request_id": rid})
        """
        return MappingProxyType({**self._state.context, **self._bound_context})

    def log(
        self,
        message: str,
        level: LogLevel,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Send a log entry to all sinks that accept ``level``."""
        state = self._state
        payload = _build_payload(state.context, self._bound_context, message, level, context)
        _dispatch(state.sinks, payload, level)

    def log_exception(
        self,
        message: str,
        exception: BaseException,
        *,
        level: LogLevel = LogLevel.ERROR,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log an exception with its type, message, and full traceback.

        Args:
            message: Descriptive message about the error.
            exception: The exception to record.
            level: Severity to log at. Defaults to ``ERROR``.
            context: Additional context (wins over the derived exception fields).
        """
        ctx = _exception_context(exception)
        if context:
            ctx.update(context)
        self.log(message, level, ctx)

    def bind(self, **context: Any) -> Logger:
        """Return a lightweight view that adds ``context`` to every entry.

        The bound view shares this logger's state, so it automatically picks up
        any later ``configure``/``set_sinks`` changes. Bound views are not
        registered and do not own lifecycle: ``close()`` on a bound view is a
        no-op.
        """
        merged = {**self._bound_context, **context}
        return Logger._from_state(self._state, merged, is_bound=True)

    def set_sinks(self, sinks: Iterable[BaseSink], *, close_removed: bool = True) -> None:
        """Replace this logger's sinks. Removed sinks are closed by default."""
        self._state.set_sinks(sinks, close_removed=close_removed)

    def add_sink(self, sink: BaseSink) -> None:
        """Add a sink to this logger."""
        self._state.add_sink(sink)

    def remove_sink(self, sink: BaseSink, *, close: bool = True) -> None:
        """Remove a sink from this logger, closing it by default."""
        self._state.remove_sink(sink, close=close)

    def close(self) -> None:
        """Close all sinks. No-op on a bound view (its sinks are shared)."""
        if self._is_bound:
            return
        self._state.close_all()

    def __enter__(self) -> Logger:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
