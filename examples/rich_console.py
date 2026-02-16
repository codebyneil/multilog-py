"""Demonstrate RichConsoleSink with styled output and pretty-printed context."""

from multilog import Logger, LogLevel
from multilog.sinks.rich_console import RichConsoleSink

logger = Logger(sinks=[RichConsoleSink()])

logger.log("Application started", LogLevel.INFO)
logger.log("Loading configuration", LogLevel.DEBUG, {"source": "env", "path": "/etc/app.toml"})
logger.log("User logged in", LogLevel.INFO, {"user_id": 42, "role": "admin"})
logger.log("High memory usage", LogLevel.WARNING, {"memory_mb": 1500, "threshold_mb": 1024})
logger.log("Database connection failed", LogLevel.ERROR, {
    "host": "db.internal",
    "port": 5432,
    "timeout_ms": 5000,
    "retries": 3,
})
logger.log("System shutdown", LogLevel.CRITICAL, {"reason": "unrecoverable", "uptime_hours": 72})
