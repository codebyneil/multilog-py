"""Custom exceptions for multilog-py."""


class MultilogError(Exception):
    """Base exception class for all multilog-py errors."""


class SinkError(MultilogError):
    """Raised when a sink fails to emit a log entry."""


class QueueFull(MultilogError):  # noqa: N818 - mirrors stdlib queue.Full, not an *Error
    """A batching sink dropped an event because its queue was full.

    Passed to a sink's ``on_error`` callback when its ``overflow_policy`` is
    ``OverflowPolicy.DROP`` and the in-memory queue has no room for a new event.
    """
