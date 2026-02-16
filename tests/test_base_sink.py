"""Tests for BaseSink: level filtering and context merging."""

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


class TestShouldLog:
    def test_default_accepts_all_levels(self):
        sink = _ConcreteSink()

        for level in LogLevel:
            assert sink._should_log(level) is True

    def test_custom_included_levels_accepts_listed(self):
        sink = _ConcreteSink(included_levels=[LogLevel.INFO, LogLevel.ERROR])

        assert sink._should_log(LogLevel.INFO) is True
        assert sink._should_log(LogLevel.ERROR) is True

    def test_custom_included_levels_rejects_unlisted(self):
        sink = _ConcreteSink(included_levels=[LogLevel.INFO, LogLevel.ERROR])

        assert sink._should_log(LogLevel.TRACE) is False
        assert sink._should_log(LogLevel.DEBUG) is False
        assert sink._should_log(LogLevel.WARNING) is False
        assert sink._should_log(LogLevel.CRITICAL) is False


class TestEmitContextMerging:
    def test_default_context_merged_into_payload(self):
        sink = _ConcreteSink(default_context={"env": "test"})

        sink.emit({"message": "hello", "level": "info"})

        payload = sink.payloads[0]
        assert payload["env"] == "test"
        assert payload["message"] == "hello"
        assert payload["level"] == "info"

    def test_payload_keys_override_default_context(self):
        sink = _ConcreteSink(default_context={"env": "test", "source": "default"})

        sink.emit({"message": "hello", "source": "override"})

        payload = sink.payloads[0]
        assert payload["source"] == "override"
        assert payload["env"] == "test"

    def test_no_default_context_passes_through_unchanged(self):
        sink = _ConcreteSink()
        original = {"message": "hello", "level": "info"}

        sink.emit(original)

        assert sink.payloads[0] is original
