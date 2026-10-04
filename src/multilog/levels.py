"""Log level enumeration for multilog-py."""

from __future__ import annotations

from enum import EnumType, StrEnum
from typing import cast, overload


class _LogLevelMeta(EnumType):
    """Metaclass enabling slice syntax on LogLevel.

    Supports:
        LogLevel[LogLevel.INFO:LogLevel.FATAL]  -> [INFO, WARN, ERROR, FATAL]
        LogLevel["info":"fatal"]                 -> same
        LogLevel["INFO":"FATAL"]                 -> same
        LogLevel[LogLevel.WARN:]                 -> [WARN, ERROR, FATAL]
        LogLevel[:LogLevel.INFO]                 -> [TRACE, DEBUG, INFO]
    """

    def _resolve_member(cls, key: LogLevel | str) -> LogLevel:
        """Resolve a member, a value string (``"info"``), or a name string (``"INFO"``)."""
        if isinstance(key, cls):
            return cast("LogLevel", key)
        try:
            return cast("LogLevel", cls(key))
        except ValueError:
            return cast("LogLevel", cls.__members__[key])

    @overload
    def __getitem__(cls, key: str) -> LogLevel: ...

    @overload
    def __getitem__(cls, key: slice) -> list[LogLevel]: ...

    def __getitem__(  # type: ignore[invalid-method-override]
        cls, key: str | slice
    ) -> LogLevel | list[LogLevel]:
        if isinstance(key, slice):
            members = cast("list[LogLevel]", list(cls))
            start = cls._resolve_member(key.start) if key.start is not None else members[0]
            stop = cls._resolve_member(key.stop) if key.stop is not None else members[-1]
            start_idx = members.index(start)
            stop_idx = members.index(stop)
            return members[start_idx : stop_idx + 1]
        return cast("LogLevel", super().__getitem__(key))


class LogLevel(StrEnum, metaclass=_LogLevelMeta):
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

    Supports slice syntax for level ranges::

        LogLevel[LogLevel.INFO:LogLevel.FATAL]
        # => [LogLevel.INFO, LogLevel.WARN, LogLevel.ERROR, LogLevel.FATAL]

    Comparison operators use severity order (not alphabetical). A level's
    value string is accepted on either side, so mixing a member with a plain
    string never falls back to ``str`` ordering::

        LogLevel.INFO >= LogLevel.DEBUG   # True
        LogLevel.INFO < LogLevel.FATAL    # True
        LogLevel.WARN >= "error"          # False (severity, not alphabetical)
    """

    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"

    def __ge__(self, other: object):
        rank = _rank_of(other)
        if rank is None:
            return NotImplemented
        return _ORDER[self] >= rank

    def __gt__(self, other: object):
        rank = _rank_of(other)
        if rank is None:
            return NotImplemented
        return _ORDER[self] > rank

    def __le__(self, other: object):
        rank = _rank_of(other)
        if rank is None:
            return NotImplemented
        return _ORDER[self] <= rank

    def __lt__(self, other: object):
        rank = _rank_of(other)
        if rank is None:
            return NotImplemented
        return _ORDER[self] < rank


#: Severity rank of each level, keyed by value string (members hash as their value).
_ORDER: dict[str, int] = {level.value: rank for rank, level in enumerate(LogLevel)}


def _rank_of(other: object) -> int | None:
    """Severity rank of a ``LogLevel`` or a level value string; ``None`` otherwise."""
    if isinstance(other, str):
        return _ORDER.get(other)
    return None


def _coerce_level(value: object) -> LogLevel:
    """Return ``value`` as a ``LogLevel`` member.

    Accepts a member, a value string (``"warn"``), or a name string (``"WARN"``).

    Raises:
        ValueError: If ``value`` is not a log level.
    """
    if isinstance(value, LogLevel):
        return value
    if isinstance(value, str):
        try:
            return LogLevel(value)
        except ValueError:
            member = LogLevel.__members__.get(value)
            if member is not None:
                return member
    valid = ", ".join(repr(level.value) for level in LogLevel)
    raise ValueError(f"{value!r} is not a LogLevel; expected a LogLevel member or one of {valid}")
