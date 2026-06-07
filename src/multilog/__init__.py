"""multilog-py — multi-destination logging with stable, reconfigurable handles.

The blessed pattern is a stable named handle plus in-place configuration::

    # anywhere, even at import time before configure() runs:
    from multilog import get_logger, LogLevel
    log = get_logger()                      # process-stable handle for "app"

    # once, at startup:
    from multilog import configure, ConsoleSink, BetterstackSink
    configure(sinks=[ConsoleSink(), BetterstackSink(token="...", ingest_url="...")])

    log.log("ready", LogLevel.INFO)         # routes to the configured sinks

``get_logger(name)`` always returns the same object for a given name, and
``configure(...)`` mutates that object in place — so a handle captured before
configuration still delivers to the sinks you install later.

A ready-to-use default handle is also exported::

    from multilog import logger
    logger.log("hello", LogLevel.INFO)
"""

from importlib.metadata import PackageNotFoundError, version

from multilog._registry import (
    configure,
    get_async_logger,
    get_logger,
)
from multilog.async_logger import AsyncLogger
from multilog.exceptions import MultilogError, QueueFull, SinkError
from multilog.levels import LogLevel
from multilog.logger import Logger
from multilog.sinks import (
    BaseSink,
    BetterstackSink,
    ConsoleSink,
    FileSink,
    OverflowPolicy,
)

try:
    __version__ = version("multilog")
except PackageNotFoundError:  # pragma: no cover - exercised in a subprocess (see test_package.py)
    __version__ = "0.0.0"

#: Ready-to-use default logger handle (equivalent to ``get_logger("app")``).
logger = get_logger()

__all__ = [
    # Registry — the primary API.
    "get_logger",
    "get_async_logger",
    "configure",
    "logger",
    # Logger types (mainly for type hints; prefer get_logger to construct).
    "Logger",
    "AsyncLogger",
    # Levels.
    "LogLevel",
    # Sinks.
    "BaseSink",
    "ConsoleSink",
    "FileSink",
    "BetterstackSink",
    "OverflowPolicy",
    # Exceptions.
    "MultilogError",
    "SinkError",
    "QueueFull",
]
