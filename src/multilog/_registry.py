"""Process-wide logger registry for multilog-py.

This is the fix for the central design gap: multilog owns logger identity and
lifecycle. ``get_logger(name)`` returns a process-stable handle, and
``configure(...)`` reconfigures that handle *in place* — it never replaces the
object. A handle captured at import time (before ``configure`` runs) therefore
keeps routing to whatever sinks ``configure`` installs later.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from multilog._core import _LoggerState
from multilog.async_logger import AsyncLogger
from multilog.logger import Logger

if TYPE_CHECKING:
    from collections.abc import Iterable

    from multilog.sinks.base import BaseSink

DEFAULT_NAME = "app"


@dataclass
class _Entry:
    """A named logger's shared state and its sync/async views.

    ``state`` is created once and never reassigned, so the views' cached
    references stay valid for the life of the process.
    """

    state: _LoggerState
    sync: Logger
    async_: AsyncLogger


_registry: dict[str, _Entry] = {}
_registry_lock = threading.Lock()


def _get_entry(name: str) -> _Entry:
    with _registry_lock:
        entry = _registry.get(name)
        if entry is None:
            state = _LoggerState(name)
            entry = _Entry(
                state=state,
                sync=Logger._from_state(state),
                async_=AsyncLogger._from_state(state),
            )
            _registry[name] = entry
        return entry


def get_logger(name: str = DEFAULT_NAME) -> Logger:
    """Return the process-stable synchronous logger for ``name``.

    ``get_logger(n) is get_logger(n)`` for the life of the process. The
    returned handle stays valid across ``configure`` calls.
    """
    return _get_entry(name).sync


def get_async_logger(name: str = DEFAULT_NAME) -> AsyncLogger:
    """Return the process-stable asynchronous logger for ``name``.

    Shares its state with ``get_logger(name)``: configuring one configures both.
    """
    return _get_entry(name).async_


def configure(
    *,
    sinks: Iterable[BaseSink] | None = None,
    context: dict[str, Any] | None = None,
    name: str = DEFAULT_NAME,
) -> Logger:
    """Reconfigure the named logger in place and return its sync handle.

    Args:
        sinks: If given, replace the logger's sinks. Sinks that are removed are
            closed (so re-configuring does not leak file handles or worker
            threads). Pass ``[]`` to remove all sinks.
        context: If given, **replace** the logger's base context. This is a
            replace, not a merge — use :meth:`Logger.bind` or
            ``configure(context={**logger.context, ...})`` to extend it.
        name: Which named logger to configure. Defaults to ``"app"``.

    Existing handles obtained via ``get_logger(name)`` / ``get_async_logger(name)``
    — including any captured before this call — observe the new configuration
    immediately, because they share the mutated state.
    """
    entry = _get_entry(name)
    if sinks is not None:
        entry.state.set_sinks(sinks)
    if context is not None:
        entry.state.set_context(context)
    return entry.sync


def _reset_registry_for_testing() -> None:
    """Reset every registered logger's state in place. For tests only.

    Entries are kept (not dropped) so handle identity is preserved across the
    reset — matching production, where handles live for the whole process. Each
    logger's sinks are closed and cleared and its context emptied, so every test
    starts from a clean configuration on the same stable handles.
    """
    with _registry_lock:
        entries = list(_registry.values())
    for entry in entries:
        entry.state.close_all()
        entry.state.set_sinks([], close_removed=False)
        entry.state.set_context(None)
