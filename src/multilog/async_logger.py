"""Asynchronous Logger for multilog-py."""

from __future__ import annotations

import asyncio
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


class AsyncLogger:
    """Asynchronous multi-destination logger.

    Mirrors :class:`~multilog.logger.Logger`. Logging methods are coroutines
    that run sink I/O on a worker thread (``asyncio.to_thread``) so the event
    loop is never blocked. The ``AsyncLogger`` and ``Logger`` for a given name
    share one underlying state, so ``configure()`` reconfigures both at once.

    Example::

        from multilog import get_async_logger, LogLevel

        log = get_async_logger()
        await log.log("Task started", LogLevel.INFO)
    """

    def __init__(
        self,
        sinks: Iterable[BaseSink] | None = None,
        context: dict[str, Any] | None = None,
        *,
        name: str = "app",
    ):
        """Create a standalone async logger with its own state.

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
    ) -> AsyncLogger:
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
        """Read-only view of the context attached to every entry from this logger."""
        return MappingProxyType({**self._state.context, **self._bound_context})

    def _emit(
        self,
        message: str,
        level: LogLevel,
        context: dict[str, Any] | None,
    ) -> None:
        state = self._state
        payload = _build_payload(state.context, self._bound_context, message, level, context)
        _dispatch(state.sinks, payload, level)

    async def log(
        self,
        message: str,
        level: LogLevel,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Send a log entry to all sinks that accept ``level``.

        Sink I/O runs on a worker thread so the event loop is not blocked.
        """
        await asyncio.to_thread(self._emit, message, level, context)

    async def log_exception(
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
        await self.log(message, level, ctx)

    def bind(self, **context: Any) -> AsyncLogger:
        """Return a lightweight view that adds ``context`` to every entry.

        Shares this logger's state, so it picks up later ``configure`` changes.
        Bound views do not own lifecycle: ``close()`` on one is a no-op.
        """
        merged = {**self._bound_context, **context}
        return AsyncLogger._from_state(self._state, merged, is_bound=True)

    def set_sinks(self, sinks: Iterable[BaseSink], *, close_removed: bool = True) -> None:
        """Replace this logger's sinks. Removed sinks are closed by default.

        Closing a removed sink runs synchronously and may briefly block; prefer
        configuring sinks at startup rather than on a hot async path.
        """
        self._state.set_sinks(sinks, close_removed=close_removed)

    def add_sink(self, sink: BaseSink) -> None:
        """Add a sink to this logger."""
        self._state.add_sink(sink)

    def remove_sink(self, sink: BaseSink, *, close: bool = True) -> None:
        """Remove a sink from this logger, closing it by default."""
        self._state.remove_sink(sink, close=close)

    async def flush(self, timeout: float | None = None) -> None:
        """Force buffered sinks to deliver now, on a worker thread. Safe on bound views."""
        await asyncio.to_thread(self._state.flush_all, timeout)

    async def close(self) -> None:
        """Close all sinks on a worker thread. No-op on a bound view."""
        if self._is_bound:
            return
        await asyncio.to_thread(self._state.close_all)

    async def __aenter__(self) -> AsyncLogger:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
