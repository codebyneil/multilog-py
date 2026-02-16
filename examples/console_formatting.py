"""Log one message at every level to see console formatting."""

from multilog import Logger, LogLevel
from multilog.sinks.console import ConsoleSink

logger = Logger(sinks=[ConsoleSink()])

logger.log("This is a trace message", LogLevel.TRACE)
logger.log("This is a debug message", LogLevel.DEBUG)
logger.log("This is an info message", LogLevel.INFO)
logger.log("This is a warning message", LogLevel.WARNING)
logger.log("This is an error message", LogLevel.ERROR)
logger.log("This is a critical message", LogLevel.CRITICAL)
logger.log("With context", LogLevel.INFO, {"user_id": 42, "action": "login"})
