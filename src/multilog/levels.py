"""Log level enumeration for multilog-py."""

from enum import StrEnum


class LogLevel(StrEnum):
    """
    Log severity levels matching OpenTelemetry specification.

    Based on OpenTelemetry log levels (severity numbers 1-24):
    - TRACE: Detailed trace information (1-4)
    - DEBUG: Debugging information (5-8)
    - INFO: Informational messages (9-12)
    - WARN: Warning conditions (13-16)
    - ERROR: Error conditions (17-20)
    - FATAL: Fatal/critical conditions (21-24)

    Inherits from str to ensure JSON serialization works properly.
    """

    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"
