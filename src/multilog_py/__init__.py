"""
multilog-py - Multi-destination logging library for Python.

Example usage:
    from multilog_py import Logger, LogLevel

    logger = Logger()  # Uses BETTERSTACK_TOKEN from env
    await logger.log("User action", LogLevel.INFO, {"user_id": 123})
"""

from multilog_py.config import Config
from multilog_py.exceptions import HandlerError, MultilogError
from multilog_py.handlers import (
    BaseHandler,
    BetterstackHandler,
    ConsoleHandler,
    FileHandler,
)
from multilog_py.levels import LogLevel
from multilog_py.logger import Logger

__version__ = "0.1.0"

__all__ = [
    "Logger",
    "LogLevel",
    "Config",
    "BaseHandler",
    "BetterstackHandler",
    "ConsoleHandler",
    "FileHandler",
    "MultilogError",
    "HandlerError",
]
