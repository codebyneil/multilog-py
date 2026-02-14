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
from multilog.config import Config
from multilog.exceptions import HandlerError, MultilogError
from multilog.handlers import (
    BaseHandler,
    BetterstackHandler,
    ConsoleHandler,
    FileHandler,
)
from multilog.levels import LogLevel
from multilog.logger import Logger

__version__ = "0.1.0"

__all__ = [
    "Logger",
    "AsyncLogger",
    "LogLevel",
    "Config",
    "BaseHandler",
    "BetterstackHandler",
    "ConsoleHandler",
    "FileHandler",
    "MultilogError",
    "HandlerError",
]
