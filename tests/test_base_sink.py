"""Tests for BaseSink: level filtering and context merging."""

from typing import Any

import pytest

from multilog.exceptions import ContextError
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


class TestContextMutation:
    def test_update_context_adds_new_keys(self):
        sink = _ConcreteSink()
        sink.update_context(env="test", region="us-east-1")

        sink.emit({"message": "hello"})

        assert sink.payloads[0]["env"] == "test"
        assert sink.payloads[0]["region"] == "us-east-1"

    def test_update_context_overwrites_existing_keys(self):
        sink = _ConcreteSink(default_context={"env": "dev"})
        sink.update_context(env="production")

        sink.emit({"message": "hello"})

        assert sink.payloads[0]["env"] == "production"

    def test_update_context_preserves_unrelated_keys(self):
        sink = _ConcreteSink(default_context={"env": "dev", "region": "us-east-1"})
        sink.update_context(env="production")

        sink.emit({"message": "hello"})

        assert sink.payloads[0]["env"] == "production"
        assert sink.payloads[0]["region"] == "us-east-1"

    def test_remove_context_removes_specified_keys(self):
        sink = _ConcreteSink(default_context={"env": "test", "region": "us-east-1"})
        sink.remove_context("env")

        sink.emit({"message": "hello"})

        assert "env" not in sink.payloads[0]
        assert sink.payloads[0]["region"] == "us-east-1"

    def test_remove_context_multiple_keys(self):
        sink = _ConcreteSink(default_context={"a": 1, "b": 2, "c": 3})
        sink.remove_context("a", "c")

        sink.emit({"message": "hello"})

        assert "a" not in sink.payloads[0]
        assert sink.payloads[0]["b"] == 2
        assert "c" not in sink.payloads[0]

    def test_remove_context_raises_on_missing_key(self):
        sink = _ConcreteSink(default_context={"env": "test"})

        with pytest.raises(ContextError, match="nonexistent"):
            sink.remove_context("nonexistent")

    def test_remove_context_raises_on_partial_missing(self):
        sink = _ConcreteSink(default_context={"env": "test"})

        with pytest.raises(ContextError, match="missing"):
            sink.remove_context("env", "missing")

        # Neither key should have been removed since validation happens first
        assert "env" in sink.default_context

    def test_clear_context_removes_all_keys(self):
        sink = _ConcreteSink(default_context={"env": "test", "region": "us-east-1"})
        sink.clear_context()

        original = {"message": "hello"}
        sink.emit(original)

        assert sink.payloads[0] is original

    def test_update_after_clear(self):
        sink = _ConcreteSink(default_context={"old": "value"})
        sink.clear_context()
        sink.update_context(new="value")

        sink.emit({"message": "hello"})

        assert "old" not in sink.payloads[0]
        assert sink.payloads[0]["new"] == "value"
