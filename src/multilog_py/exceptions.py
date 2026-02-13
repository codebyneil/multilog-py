"""Custom exceptions for multilog-py."""


class MultilogError(Exception):
    """Base exception class for all multilog-py errors."""

    pass


class HandlerError(MultilogError):
    """Raised when a handler fails to emit a log entry."""

    pass
