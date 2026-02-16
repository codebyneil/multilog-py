"""Custom exceptions for multilog-py."""


class MultilogError(Exception):
    """Base exception class for all multilog-py errors."""

    pass


class ConfigError(MultilogError):
    """Raised when logger configuration is invalid or incomplete."""

    pass


class SinkError(MultilogError):
    """Raised when a sink fails to emit a log entry."""

    pass
