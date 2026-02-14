"""Custom exceptions for multilog-py."""


class MultilogError(Exception):
    """Base exception class for all multilog-py errors."""

    pass


class SinkError(MultilogError):
    """Raised when a sink fails to emit a log entry."""

    pass
