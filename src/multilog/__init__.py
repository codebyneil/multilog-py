"""
multilog-py - Multi-destination logging library for Python.

Example usage (synchronous):
    from multilog import Logger, LogLevel

    logger = Logger()  # Uses BETTERSTACK_TOKEN from env
    logger.log("User action", LogLevel.INFO, {"user_id": 123})

Example usage (asynchronous):
    from multilog import AsyncLogger, LogLevel

    logger = AsyncLogger()
    await logger.log("User action", LogLevel.INFO, {"user_id": 123})
"""

from multilog.async_logger import AsyncLogger
from multilog.exceptions import MultilogError, SinkError
from multilog.levels import LogLevel
from multilog.logger import Logger
from multilog.sinks import (
    BaseSink,
    BetterstackSink,
    ConsoleSink,
    FileSink,
)

__version__ = "0.1.0"

__all__ = [
    "Logger",
    "AsyncLogger",
    "LogLevel",
    "BaseSink",
    "BetterstackSink",
    "ConsoleSink",
    "FileSink",
    "MultilogError",
    "SinkError",
]
