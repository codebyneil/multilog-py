"""Targeted coverage for BetterstackSink edge paths.

Complements test_betterstack_sink.py with shutdown, atexit, deadline, and
error-handler corner cases.
"""

import threading
import time

from pytest_httpx import HTTPXMock

from multilog import BetterstackSink
from multilog.sinks.betterstack import _STOP

INGEST_URL = "https://in.logs.example.com"


def _payload(message="hi"):
    return {"message": message, "level": "info", "timestamp_ms": 1_700_000_000_000}


class TestAtexit:
    def test_register_and_unregister_on_close(self):
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL, batch=True)  # atexit on by default
        assert sink._atexit_registered is True
        sink.close()
        assert sink._atexit_registered is False

    def test_no_registration_when_disabled(self):
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL, batch=True, register_atexit=False)
        assert sink._atexit_registered is False
        sink.close()


class TestEnqueueAfterClose:
    def test_emit_after_close_is_silently_dropped(self):
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL, batch=True, register_atexit=False)
        sink.close()
        # Must not raise; event is dropped because the sink is closed.
        sink._emit(_payload("too late"))
        assert sink._queue is not None
        assert sink._queue.empty()


class TestWorkerIdle:
    def test_worker_survives_idle_flush_intervals(self):
        """With no events, the worker loops through the empty-queue path and stays alive."""
        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            batch=True,
            flush_interval=0.02,
            register_atexit=False,
        )
        time.sleep(0.1)  # several idle flush intervals
        assert sink._worker is not None and sink._worker.is_alive()
        sink.close()
        assert not sink._worker.is_alive()


class TestDeadline:
    def test_send_breaks_when_deadline_passed(self, monkeypatch):
        errors: list = []
        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            batch=False,
            register_atexit=False,
            on_error=lambda e, p: errors.append((e, p)),
        )
        posted: list = []
        monkeypatch.setattr(sink._client, "post", lambda *a, **k: posted.append(1))

        sink._deadline = time.monotonic() - 1  # already past
        sink._send([_payload()])

        assert posted == []  # never attempted a POST
        assert errors == []  # no last_exc, so no on_error
        sink.close()

    def test_sleep_backoff_sleeps_within_future_deadline(self, monkeypatch):
        slept: list[float] = []
        monkeypatch.setattr("multilog.sinks.betterstack.time.sleep", slept.append)
        monkeypatch.setattr("multilog.sinks.betterstack.random.uniform", lambda _a, b: b)

        sink = BetterstackSink(
            token="t", ingest_url=INGEST_URL, batch=False, register_atexit=False, backoff_base=0.5
        )
        sink._deadline = time.monotonic() + 100  # plenty of room
        sink._sleep_backoff(1)

        assert len(slept) == 1 and slept[0] > 0
        sink.close()

    def test_sleep_backoff_clamped_to_zero_past_deadline(self, monkeypatch):
        slept: list[float] = []
        monkeypatch.setattr("multilog.sinks.betterstack.time.sleep", slept.append)
        monkeypatch.setattr("multilog.sinks.betterstack.random.uniform", lambda _a, b: b)

        sink = BetterstackSink(token="t", ingest_url=INGEST_URL, batch=False, register_atexit=False)
        sink._deadline = time.monotonic() - 1  # past -> remaining clamped to 0
        sink._sleep_backoff(3)

        assert slept == []  # delay clamped to 0, no sleep
        sink.close()


class TestOnErrorRobustness:
    def test_on_error_that_raises_is_swallowed(self, httpx_mock: HTTPXMock, monkeypatch, capsys):
        httpx_mock.add_response(url=INGEST_URL, status_code=503, is_reusable=True)

        def boom(_exc, _payloads):
            raise ValueError("on_error itself blew up")

        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            batch=False,
            register_atexit=False,
            max_retries=0,
            on_error=boom,
        )
        monkeypatch.setattr(sink, "_sleep_backoff", lambda _a: None)

        sink._emit(_payload())  # must not raise despite on_error raising

        assert "ValueError" in capsys.readouterr().err
        sink.close()


class TestReportUnflushed:
    def test_undelivered_events_reported_at_close(self, monkeypatch):
        errors: list = []
        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            batch=True,
            flush_interval=0.02,
            register_atexit=False,
            on_error=lambda e, p: errors.append((e, p)),
        )

        # Park the worker inside its first _send so the queue never drains.
        started = threading.Event()
        release = threading.Event()
        calls: list = []

        def blocking_send(payloads):
            calls.append(list(payloads))
            if len(calls) == 1:
                started.set()
                release.wait(timeout=5)

        monkeypatch.setattr(sink, "_send", blocking_send)

        sink._emit(_payload("A"))  # worker grabs A and parks
        assert started.wait(2)
        sink._emit(_payload("B"))  # stuck in the queue
        sink._emit(_payload("C"))  # stuck in the queue

        sink.close(flush_timeout=0.1)  # join times out -> report the remainder

        assert len(errors) == 1
        exc, payloads = errors[0]
        assert isinstance(exc, TimeoutError)
        assert {p["message"] for p in payloads} == {"B", "C"}

        # Let the parked worker exit cleanly.
        release.set()
        sink._queue.put(_STOP)


class TestCollectBatchFull:
    def test_collect_stops_at_batch_size(self, monkeypatch):
        """A single collect drains at most batch_size, leaving the rest queued."""
        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            batch=True,
            batch_size=2,
            flush_interval=0.02,
            register_atexit=False,
        )

        started = threading.Event()
        release = threading.Event()
        calls: list = []

        def blocking_send(payloads):
            calls.append(list(payloads))
            if len(calls) == 1:
                started.set()
                release.wait(timeout=5)

        monkeypatch.setattr(sink, "_send", blocking_send)

        sink._emit(_payload("A"))  # worker grabs A and parks; queue now empty
        assert started.wait(2)

        assert sink._queue is not None
        sink._queue.put_nowait(_payload("B"))
        sink._queue.put_nowait(_payload("C"))
        sink._queue.put_nowait(_payload("D"))

        batch, stop = sink._collect_batch(block=False)
        assert len(batch) == 2  # filled to batch_size, did not take all three
        assert stop is False

        release.set()
        sink.close(flush_timeout=0.5)
