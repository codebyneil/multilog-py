"""Tests for the AsyncLogger."""

import asyncio
import threading
from typing import Any

import pytest
from conftest import RaisingSink, RecordingSink

from multilog import AsyncLogger, LogLevel
from multilog.sinks.base import BaseSink


class _ThreadCapturingSink(BaseSink):
    """Records which thread each emit ran on."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.threads: list[int] = []
        self.payloads: list[dict[str, Any]] = []

    def _emit(self, payload: dict[str, Any]) -> None:
        self.threads.append(threading.get_ident())
        self.payloads.append(payload)


class TestAsyncDispatch:
    async def test_log_emits_to_all_sinks(self):
        a, b = RecordingSink(), RecordingSink()
        logger = AsyncLogger(sinks=[a, b])

        await logger.log("hello", LogLevel.INFO)

        assert a.payloads[0]["message"] == "hello"
        assert b.payloads[0]["message"] == "hello"

    async def test_context_dict_merges_into_payload(self):
        sink = RecordingSink()
        logger = AsyncLogger(sinks=[sink])

        await logger.log("hi", LogLevel.INFO, {"user_id": 7})

        assert sink.payloads[0]["user_id"] == 7

    async def test_min_level_filter_applies(self):
        sink = RecordingSink(min_level=LogLevel.WARN)
        logger = AsyncLogger(sinks=[sink])

        await logger.log("dropped", LogLevel.INFO)
        await logger.log("kept", LogLevel.ERROR)

        assert [p["message"] for p in sink.payloads] == ["kept"]

    async def test_log_exception_dispatches(self):
        sink = RecordingSink()
        logger = AsyncLogger(sinks=[sink])

        try:
            raise ValueError("boom")
        except ValueError as e:
            await logger.log_exception("failed", e)

        payload = sink.payloads[0]
        assert payload["exception_type"] == "ValueError"
        assert payload["exception_message"] == "boom"
        assert payload["level"] == LogLevel.ERROR

    async def test_log_exception_custom_level(self):
        sink = RecordingSink()
        logger = AsyncLogger(sinks=[sink])

        await logger.log_exception("warn-level", RuntimeError("x"), level=LogLevel.WARN)

        assert sink.payloads[0]["level"] == LogLevel.WARN


class TestRunsOffEventLoop:
    async def test_emit_runs_in_worker_thread(self):
        sink = _ThreadCapturingSink()
        logger = AsyncLogger(sinks=[sink])

        await logger.log("hi", LogLevel.INFO)

        assert sink.threads[0] != threading.get_ident()


class TestBind:
    async def test_bound_async_logger_merges_context(self):
        sink = RecordingSink()
        logger = AsyncLogger(sinks=[sink]).bind(request_id="abc")

        await logger.log("hi", LogLevel.INFO)

        assert sink.payloads[0]["request_id"] == "abc"


class TestConcurrentEmits:
    async def test_no_payloads_lost_under_high_concurrency(self):
        sink = RecordingSink()
        logger = AsyncLogger(sinks=[sink])

        n = 200
        await asyncio.gather(*[logger.log(f"msg-{i}", LogLevel.INFO, {"i": i}) for i in range(n)])

        assert len(sink.payloads) == n
        seen = {p["i"] for p in sink.payloads}
        assert seen == set(range(n))


class TestDispatchIsolation:
    async def test_one_failing_sink_does_not_break_others(self, capsys):
        good = RecordingSink()
        bad = RaisingSink(RuntimeError("kaboom"))
        logger = AsyncLogger(sinks=[bad, good])

        await logger.log("hi", LogLevel.INFO)

        assert len(good.payloads) == 1
        assert "RaisingSink failed to emit" in capsys.readouterr().err


class TestCloseAndContextManager:
    async def test_close_calls_close_on_each_sink(self):
        a, b = RecordingSink(), RecordingSink()
        logger = AsyncLogger(sinks=[a, b])

        await logger.close()

        assert a.close_calls == 1
        assert b.close_calls == 1

    async def test_async_context_manager_closes_on_exit(self):
        sink = RecordingSink()

        async with AsyncLogger(sinks=[sink]) as logger:
            await logger.log("inside", LogLevel.INFO)

        assert sink.close_calls == 1
        assert sink.payloads[0]["message"] == "inside"

    async def test_async_context_manager_closes_on_exception(self):
        sink = RecordingSink()

        with pytest.raises(ValueError):
            async with AsyncLogger(sinks=[sink]) as logger:
                await logger.log("before-raise", LogLevel.INFO)
                raise ValueError("propagate me")

        assert sink.close_calls == 1
