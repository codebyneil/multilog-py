"""Tests for default_context mutation on Logger, AsyncLogger, and _LoggerCore."""

import asyncio
from typing import Any

import pytest

from multilog._core import _LoggerCore
from multilog.async_logger import AsyncLogger
from multilog.exceptions import ContextError
from multilog.levels import LogLevel
from multilog.logger import Logger
from multilog.sinks.base import BaseSink


class _RecordingSink(BaseSink):
    """Sink that captures emitted payloads for test assertions."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.payloads: list[dict[str, Any]] = []

    def _emit(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)


class TestLoggerCoreContextMutation:
    def test_update_context_appears_in_payload(self):
        sink = _RecordingSink()
        core = _LoggerCore(sinks=[sink])
        core.update_context(service="auth")

        core.log("test", LogLevel.INFO)

        assert sink.payloads[0]["service"] == "auth"

    def test_remove_context_removes_from_payload(self):
        sink = _RecordingSink()
        core = _LoggerCore(sinks=[sink], default_context={"service": "auth", "env": "dev"})
        core.remove_context("service")

        core.log("test", LogLevel.INFO)

        assert "service" not in sink.payloads[0]
        assert sink.payloads[0]["env"] == "dev"

    def test_remove_context_raises_on_missing_key(self):
        core = _LoggerCore(sinks=[])

        with pytest.raises(ContextError, match="nonexistent"):
            core.remove_context("nonexistent")

    def test_clear_context_removes_all(self):
        sink = _RecordingSink()
        core = _LoggerCore(sinks=[sink], default_context={"service": "auth", "env": "dev"})
        core.clear_context()

        core.log("test", LogLevel.INFO)

        assert "service" not in sink.payloads[0]
        assert "env" not in sink.payloads[0]

    def test_per_call_content_overrides_updated_context(self):
        sink = _RecordingSink()
        core = _LoggerCore(sinks=[sink])
        core.update_context(service="auth")

        core.log("test", LogLevel.INFO, {"service": "override"})

        assert sink.payloads[0]["service"] == "override"


class TestLoggerContextMutation:
    def test_update_context(self):
        sink = _RecordingSink()
        logger = Logger(sinks=[sink])
        logger.update_context(service="auth")

        logger.log("test", LogLevel.INFO)

        assert sink.payloads[0]["service"] == "auth"

    def test_remove_context(self):
        sink = _RecordingSink()
        logger = Logger(sinks=[sink], default_context={"service": "auth"})
        logger.remove_context("service")

        logger.log("test", LogLevel.INFO)

        assert "service" not in sink.payloads[0]

    def test_remove_context_raises_on_missing_key(self):
        logger = Logger(sinks=[])

        with pytest.raises(ContextError):
            logger.remove_context("nonexistent")

    def test_clear_context(self):
        sink = _RecordingSink()
        logger = Logger(sinks=[sink], default_context={"service": "auth"})
        logger.clear_context()

        logger.log("test", LogLevel.INFO)

        assert "service" not in sink.payloads[0]


class TestAsyncLoggerContextMutation:
    def test_update_context_is_sync(self):
        logger = AsyncLogger(sinks=[])
        assert not asyncio.iscoroutinefunction(logger.update_context)

    def test_remove_context_is_sync(self):
        logger = AsyncLogger(sinks=[])
        assert not asyncio.iscoroutinefunction(logger.remove_context)

    def test_clear_context_is_sync(self):
        logger = AsyncLogger(sinks=[])
        assert not asyncio.iscoroutinefunction(logger.clear_context)

    def test_updated_context_appears_in_async_log(self):
        async def _run():
            sink = _RecordingSink()
            logger = AsyncLogger(sinks=[sink])
            logger.update_context(service="auth")
            await logger.log("test", LogLevel.INFO)
            assert sink.payloads[0]["service"] == "auth"

        asyncio.run(_run())

    def test_removed_context_absent_from_async_log(self):
        async def _run():
            sink = _RecordingSink()
            logger = AsyncLogger(sinks=[sink], default_context={"service": "auth"})
            logger.remove_context("service")
            await logger.log("test", LogLevel.INFO)
            assert "service" not in sink.payloads[0]

        asyncio.run(_run())

    def test_remove_context_raises_on_missing_key(self):
        logger = AsyncLogger(sinks=[])

        with pytest.raises(ContextError):
            logger.remove_context("nonexistent")


class TestFullPrecedenceChain:
    """Verify merge precedence: sink context < logger context < call content."""

    def test_logger_context_overrides_sink_context(self):
        sink = _RecordingSink(default_context={"source": "sink"})
        logger = Logger(sinks=[sink])
        logger.update_context(source="logger")

        logger.log("test", LogLevel.INFO)

        assert sink.payloads[0]["source"] == "logger"

    def test_call_content_overrides_logger_context(self):
        sink = _RecordingSink()
        logger = Logger(sinks=[sink])
        logger.update_context(source="logger")

        logger.log("test", LogLevel.INFO, {"source": "call"})

        assert sink.payloads[0]["source"] == "call"

    def test_call_content_overrides_both(self):
        sink = _RecordingSink(default_context={"source": "sink"})
        logger = Logger(sinks=[sink])
        logger.update_context(source="logger")

        logger.log("test", LogLevel.INFO, {"source": "call"})

        assert sink.payloads[0]["source"] == "call"
