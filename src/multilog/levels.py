"""Log level enumeration for multilog-py."""

from enum import EnumType, StrEnum


class _LogLevelMeta(EnumType):
    """Metaclass enabling slice syntax on LogLevel.

    Supports:
        LogLevel[LogLevel.INFO:LogLevel.FATAL]  -> [INFO, WARN, ERROR, FATAL]
        LogLevel["info":"fatal"]                 -> same
        LogLevel["INFO":"FATAL"]                 -> same
        LogLevel[LogLevel.WARN:]                 -> [WARN, ERROR, FATAL]
        LogLevel[:LogLevel.INFO]                 -> [TRACE, DEBUG, INFO]
    """

    def _resolve_member(cls, key):
        """Resolve a string or member to a LogLevel member."""
        if isinstance(key, cls):
            return key
        try:
            return cls(key)
        except ValueError:
            return cls._member_map_[key]

    def __getitem__(cls, key):
        if isinstance(key, slice):
            members = list(cls)
            start = cls._resolve_member(key.start) if key.start is not None else members[0]
            stop = cls._resolve_member(key.stop) if key.stop is not None else members[-1]
            start_idx = members.index(start)
            stop_idx = members.index(stop)
            return members[start_idx : stop_idx + 1]
        return super().__getitem__(key)


class LogLevel(StrEnum, metaclass=_LogLevelMeta):
    """
    Log severity levels matching OpenTelemetry specification.

    Based on OpenTelemetry log levels (severity numbers 1-24):
    - TRACE: Detailed trace information (1-4)
    - DEBUG: Debugging information (5-8)
    - INFO: Informational messages (9-12)
    - WARNING: Warning conditions (13-16)
    - ERROR: Error conditions (17-20)
    - CRITICAL: Critical/fatal conditions (21-24)

    Inherits from str to ensure JSON serialization works properly.

    Supports slice syntax for level ranges::

        LogLevel[LogLevel.INFO:LogLevel.CRITICAL]
        # => [LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL]

    Comparison operators use severity order (not alphabetical)::

        LogLevel.INFO >= LogLevel.DEBUG    # True
        LogLevel.INFO < LogLevel.CRITICAL  # True

    ``WARN`` and ``FATAL`` are accepted as aliases for backward compatibility::

        LogLevel.WARN is LogLevel.WARNING   # True
        LogLevel.FATAL is LogLevel.CRITICAL # True
        LogLevel("warn") is LogLevel.WARNING  # True (via _missing_)
    """

    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    # Backward-compatible aliases
    WARN = WARNING
    FATAL = CRITICAL

    @classmethod
    def _missing_(cls, value):
        """Resolve legacy level values for backward compatibility."""
        aliases = {"warn": cls.WARNING, "fatal": cls.CRITICAL}
        return aliases.get(value)

    def __ge__(self, other):
        if isinstance(other, LogLevel):
            members = list(LogLevel)
            return members.index(self) >= members.index(other)
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, LogLevel):
            members = list(LogLevel)
            return members.index(self) > members.index(other)
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, LogLevel):
            members = list(LogLevel)
            return members.index(self) <= members.index(other)
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, LogLevel):
            members = list(LogLevel)
            return members.index(self) < members.index(other)
        return NotImplemented
