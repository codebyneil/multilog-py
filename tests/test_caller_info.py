"""Tests for automatic caller info (file, line, function) in log payloads."""

import asyncio
from typing import Any

from multilog.async_logger import AsyncLogger
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


class TestLoggerCallerInfo:
    def test_log_includes_caller_file(self):
        sink = _RecordingSink()
        logger = Logger(sinks=[sink])

        logger.log("test", LogLevel.INFO)

        assert sink.payloads[0]["caller_file"] == __file__

    def test_log_includes_caller_line(self):
        sink = _RecordingSink()
        logger = Logger(sinks=[sink])

        logger.log("test", LogLevel.INFO)

        assert isinstance(sink.payloads[0]["caller_line"], int)
        assert sink.payloads[0]["caller_line"] > 0

    def test_log_includes_caller_function(self):
        sink = _RecordingSink()
        logger = Logger(sinks=[sink])

        logger.log("test", LogLevel.INFO)

        assert sink.payloads[0]["caller_function"] == "test_log_includes_caller_function"

    def test_log_endpoint_includes_caller_info(self):
        sink = _RecordingSink()
        logger = Logger(sinks=[sink])

        logger.log_endpoint("test_ep", "GET", "/path", {"Host": "localhost"})

        payload = sink.payloads[0]
        assert payload["caller_file"] == __file__
        assert payload["caller_function"] == "test_log_endpoint_includes_caller_info"

    def test_log_exception_includes_caller_info(self):
        sink = _RecordingSink()
        logger = Logger(sinks=[sink])

        logger.log_exception("boom", ValueError("bad value"))

        payload = sink.payloads[0]
        assert payload["caller_file"] == __file__
        assert payload["caller_function"] == "test_log_exception_includes_caller_info"

    def test_per_call_content_overrides_caller_info(self):
        sink = _RecordingSink()
        logger = Logger(sinks=[sink])

        logger.log("test", LogLevel.INFO, {"caller_file": "custom.py"})

        assert sink.payloads[0]["caller_file"] == "custom.py"

    def test_caller_line_points_to_log_call(self):
        sink = _RecordingSink()
        logger = Logger(sinks=[sink])

        # Capture the exact line number of the log call
        import inspect
        expected_line = inspect.currentframe().f_lineno + 1
        logger.log("test", LogLevel.INFO)

        assert sink.payloads[0]["caller_line"] == expected_line


class TestAsyncLoggerCallerInfo:
    def test_async_log_includes_caller_file(self):
        async def _run():
            sink = _RecordingSink()
            logger = AsyncLogger(sinks=[sink])

            await logger.log("test", LogLevel.INFO)

            assert sink.payloads[0]["caller_file"] == __file__

        asyncio.run(_run())

    def test_async_log_includes_caller_function(self):
        async def _run():
            sink = _RecordingSink()
            logger = AsyncLogger(sinks=[sink])

            await logger.log("test", LogLevel.INFO)

            assert sink.payloads[0]["caller_function"] == "_run"

        asyncio.run(_run())

    def test_async_log_endpoint_includes_caller_info(self):
        async def _run():
            sink = _RecordingSink()
            logger = AsyncLogger(sinks=[sink])

            await logger.log_endpoint("ep", "POST", "/api", {"Content-Type": "application/json"})

            payload = sink.payloads[0]
            assert payload["caller_file"] == __file__
            assert payload["caller_function"] == "_run"

        asyncio.run(_run())

    def test_async_log_exception_includes_caller_info(self):
        async def _run():
            sink = _RecordingSink()
            logger = AsyncLogger(sinks=[sink])

            await logger.log_exception("err", RuntimeError("fail"))

            payload = sink.payloads[0]
            assert payload["caller_file"] == __file__
            assert payload["caller_function"] == "_run"

        asyncio.run(_run())

    def test_async_per_call_content_overrides_caller_info(self):
        async def _run():
            sink = _RecordingSink()
            logger = AsyncLogger(sinks=[sink])

            await logger.log("test", LogLevel.INFO, {"caller_function": "override"})

            assert sink.payloads[0]["caller_function"] == "override"

        asyncio.run(_run())
