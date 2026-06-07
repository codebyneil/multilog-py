"""Tests for BaseSink: threshold and explicit-set level filtering."""

from typing import Any

from multilog.levels import LogLevel
from multilog.sinks.base import BaseSink


class _ConcreteSink(BaseSink):
    """Minimal concrete sink that records emitted payloads."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.payloads: list[dict[str, Any]] = []

    def _emit(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)


class TestAcceptsThreshold:
    def test_default_accepts_all_levels(self):
        sink = _ConcreteSink()
        for level in LogLevel:
            assert sink._accepts(level) is True

    def test_min_level_accepts_at_or_above(self):
        sink = _ConcreteSink(min_level=LogLevel.WARN)
        assert sink._accepts(LogLevel.WARN) is True
        assert sink._accepts(LogLevel.ERROR) is True
        assert sink._accepts(LogLevel.FATAL) is True

    def test_min_level_rejects_below(self):
        sink = _ConcreteSink(min_level=LogLevel.WARN)
        assert sink._accepts(LogLevel.TRACE) is False
        assert sink._accepts(LogLevel.DEBUG) is False
        assert sink._accepts(LogLevel.INFO) is False


class TestAcceptsOnly:
    def test_only_accepts_listed(self):
        sink = _ConcreteSink(only={LogLevel.INFO, LogLevel.ERROR})
        assert sink._accepts(LogLevel.INFO) is True
        assert sink._accepts(LogLevel.ERROR) is True

    def test_only_rejects_unlisted(self):
        sink = _ConcreteSink(only={LogLevel.INFO, LogLevel.ERROR})
        assert sink._accepts(LogLevel.TRACE) is False
        assert sink._accepts(LogLevel.WARN) is False
        assert sink._accepts(LogLevel.FATAL) is False

    def test_only_overrides_min_level(self):
        # min_level would admit FATAL, but only restricts to INFO.
        sink = _ConcreteSink(min_level=LogLevel.FATAL, only={LogLevel.INFO})
        assert sink._accepts(LogLevel.INFO) is True
        assert sink._accepts(LogLevel.FATAL) is False


class TestEmit:
    def test_emit_passes_payload_through_to_emit(self):
        sink = _ConcreteSink()
        original = {"message": "hello", "level": "info"}

        sink.emit(original)

        assert sink.payloads[0] is original

    def test_default_close_is_noop(self):
        sink = _ConcreteSink()
        sink.close()  # must not raise

    def test_default_flush_returns_true(self):
        sink = _ConcreteSink()
        assert sink.flush() is True
        assert sink.flush(timeout=1.0) is True
