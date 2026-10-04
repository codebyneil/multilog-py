"""Shutdown and backpressure guarantees for the batching BetterstackSink.

Every event the sink accepts is either delivered or reported to ``on_error``
exactly once — including events still pending when ``close()``'s drain deadline
expires with a dead destination — and ``flush()`` / ``close()`` honor their
timeouts even when the queue is full or the worker is stuck.
"""

import threading
import time

import httpx
import pytest
from pytest_httpx import HTTPXMock

from multilog import BetterstackSink

INGEST_URL = "https://in.logs.example.com"


def _payload(i: int) -> dict:
    return {"message": str(i), "level": "info", "timestamp_ms": 1_700_000_000_000}


def _sink(**kwargs) -> BetterstackSink:
    return BetterstackSink(token="t", ingest_url=INGEST_URL, register_atexit=False, **kwargs)


def _park_worker(sink, monkeypatch):
    """Park the worker inside its first _send so the queue stops draining."""
    started = threading.Event()
    release = threading.Event()
    calls: list = []

    def blocking_send(payloads):
        calls.append(list(payloads))
        if len(calls) == 1:
            started.set()
            release.wait(timeout=5)

    monkeypatch.setattr(sink, "_send", blocking_send)
    return started, release


class TestNoSilentLossAtClose:
    def test_every_event_reported_exactly_once_when_destination_refuses(
        self, httpx_mock: HTTPXMock, monkeypatch
    ):
        """Regression: with the destination down, close() used to drop most of the queue
        with no on_error call (the worker raced close()'s own drain for the queue and
        then skipped delivery because the deadline had passed)."""
        httpx_mock.add_exception(httpx.ConnectError("refused"), is_reusable=True)
        monkeypatch.setattr("multilog.sinks.betterstack.random.uniform", lambda _a, b: b)
        reported: list[str] = []
        sink = _sink(
            batch=True,
            batch_size=5,
            flush_interval=0.02,
            max_retries=3,
            backoff_base=10.0,
            backoff_max=10.0,
            on_error=lambda _e, p: reported.extend(x["message"] for x in p),
        )
        n = 60
        for i in range(n):
            sink._emit(_payload(i))
        time.sleep(0.1)  # worker has a batch in flight and is inside a long backoff

        sink.close(flush_timeout=0.3)

        assert sink._worker is not None
        sink._worker.join(timeout=5)
        assert not sink._worker.is_alive()
        assert sorted(reported, key=int) == [str(i) for i in range(n)]  # each exactly once

    def test_worker_exits_after_close_drained_the_stop_sentinel(self, monkeypatch):
        """When close() times out and drains the queue itself (consuming _STOP), the
        worker must still stop instead of polling forever."""
        sink = _sink(batch=True, flush_interval=0.02, on_error=lambda _e, _p: None)
        started, release = _park_worker(sink, monkeypatch)

        sink._emit(_payload(0))  # worker takes it and parks in _send
        assert started.wait(2)
        sink._emit(_payload(1))  # left in the queue

        sink.close(flush_timeout=0.1)  # join times out; close() drains the queue + _STOP

        release.set()
        assert sink._worker is not None
        sink._worker.join(timeout=2)
        assert not sink._worker.is_alive()


class TestTimeoutsHonoredOnFullQueue:
    def test_flush_returns_false_within_timeout_when_queue_is_full(self, monkeypatch):
        sink = _sink(batch=True, queue_size=2, on_error=lambda _e, _p: None)
        started, release = _park_worker(sink, monkeypatch)

        sink._emit(_payload(0))
        assert started.wait(2)
        sink._emit(_payload(1))
        sink._emit(_payload(2))  # queue full

        t0 = time.monotonic()
        assert sink.flush(timeout=0.2) is False
        assert time.monotonic() - t0 < 1.0  # used to block until the worker freed space

        release.set()
        sink.close(flush_timeout=1.0)

    def test_close_returns_within_flush_timeout_when_queue_is_full(self, monkeypatch):
        reported: list = []
        sink = _sink(batch=True, queue_size=2, on_error=lambda _e, p: reported.extend(p))
        started, release = _park_worker(sink, monkeypatch)

        sink._emit(_payload(0))
        assert started.wait(2)
        sink._emit(_payload(1))
        sink._emit(_payload(2))  # queue full

        t0 = time.monotonic()
        sink.close(flush_timeout=0.2)
        assert time.monotonic() - t0 < 1.0  # used to block on put(_STOP) indefinitely
        assert {p["message"] for p in reported} == {"1", "2"}  # backlog reported, not lost

        release.set()
        assert sink._worker is not None
        sink._worker.join(timeout=2)
        assert not sink._worker.is_alive()


class TestCloseInterruptsBackoff:
    def test_close_wakes_backoff_and_delivers_within_deadline(
        self, httpx_mock: HTTPXMock, monkeypatch
    ):
        """A backoff sleep that began before close() must not outlive the drain
        deadline: closing wakes the worker, which retries and delivers."""
        httpx_mock.add_exception(httpx.ConnectError("blip"))
        httpx_mock.add_response(url=INGEST_URL, status_code=202, is_reusable=True)
        monkeypatch.setattr("multilog.sinks.betterstack.random.uniform", lambda _a, b: b)
        errors: list = []
        sink = _sink(
            batch=True,
            flush_interval=0.02,
            max_retries=3,
            backoff_base=30.0,
            backoff_max=30.0,
            on_error=lambda e, _p: errors.append(e),
        )

        sink._emit(_payload(0))
        deadline = time.monotonic() + 3
        while len(httpx_mock.get_requests()) < 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        # The worker is now inside a 30s backoff that started before close().

        t0 = time.monotonic()
        sink.close(flush_timeout=5.0)

        assert time.monotonic() - t0 < 2.0
        assert len(httpx_mock.get_requests()) == 2  # retried promptly and succeeded
        assert errors == []


class TestUnexpectedClientErrors:
    def test_non_httpx_exception_is_reported_and_worker_survives(
        self, httpx_mock: HTTPXMock, monkeypatch
    ):
        """httpx raises a plain RuntimeError when a closed client is used; any such
        non-transport error must be reported, not retried, and must not kill the worker."""
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        errors: list = []
        sink = _sink(batch=True, flush_interval=0.02, on_error=lambda e, p: errors.append((e, p)))
        real_post = sink._client.post
        calls: list = []

        def flaky_post(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("Cannot send a request, as the client has been closed.")
            return real_post(*args, **kwargs)

        monkeypatch.setattr(sink._client, "post", flaky_post)

        sink._emit(_payload(0))
        assert sink.flush(timeout=5) is True
        assert len(errors) == 1
        assert isinstance(errors[0][0], RuntimeError)
        assert errors[0][1] == (_payload(0),)
        assert len(calls) == 1  # not retried

        sink._emit(_payload(1))
        assert sink.flush(timeout=5) is True
        assert len(httpx_mock.get_requests()) == 1  # worker alive; next batch delivered
        sink.close()

    def test_bug_inside_send_is_reported_and_worker_survives(self, monkeypatch):
        errors: list = []
        sink = _sink(batch=True, flush_interval=0.02, on_error=lambda e, p: errors.append((e, p)))

        def exploding_send(_payloads):
            raise ValueError("bug")

        monkeypatch.setattr(sink, "_send", exploding_send)

        sink._emit(_payload(0))
        assert sink.flush(timeout=5) is True
        assert len(errors) == 1
        assert isinstance(errors[0][0], ValueError)
        assert errors[0][1] == (_payload(0),)
        assert sink._worker is not None and sink._worker.is_alive()
        sink.close()


class TestFlushRaces:
    def test_flush_marker_enqueued_as_sink_closes_does_not_hang(self, monkeypatch):
        """If close() completes between flush()'s closed-check and its enqueue, the
        drain has already run and nobody would signal the marker: flush() must
        notice and return instead of waiting forever."""
        sink = _sink(batch=True, flush_interval=0.02)
        assert sink._queue is not None
        real_put = sink._queue.put

        def put_then_close(item, *args, **kwargs):
            real_put(item, *args, **kwargs)
            sink._closed = True  # simulate close() finishing right after the marker lands

        monkeypatch.setattr(sink._queue, "put", put_then_close)

        assert sink.flush(timeout=None) is True  # must not block forever

        sink._closed = False  # let the real close() run
        sink.close()


class TestRetryAfterCap:
    def test_retry_after_is_clamped_to_retry_after_max(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_response(url=INGEST_URL, status_code=429, headers={"Retry-After": "3600"})
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _sink(batch=False, max_retries=3, retry_after_max=0.5)
        slept: list[float] = []
        monkeypatch.setattr(sink, "_sleep", slept.append)

        sink._emit(_payload(0))

        assert slept == [0.5]  # an hour-long Retry-After cannot stall delivery
        sink.close()

    def test_zero_retry_after_does_not_wait(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_response(url=INGEST_URL, status_code=429, headers={"Retry-After": "0"})
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _sink(batch=False, max_retries=3)
        waited: list[float] = []
        monkeypatch.setattr(sink._stop_event, "wait", waited.append)

        sink._emit(_payload(0))

        assert waited == []
        assert len(httpx_mock.get_requests()) == 2
        sink.close()


class TestConstructorValidation:
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"batch_size": 0},
            {"flush_interval": 0},  # would busy-spin the worker
            {"flush_interval": -1},  # would kill the worker with a ValueError from queue.get
            {"queue_size": 0},  # queue.Queue(maxsize=0) is unbounded; overflow never triggers
            {"max_retries": -1},  # range(0): no attempt at all, event dropped unreported
            {"timeout": 0},
            {"backoff_base": -0.1},
            {"backoff_max": -1},
            {"retry_after_max": -1},
            {"flush_timeout": -1},
        ],
    )
    def test_out_of_range_option_raises_value_error(self, kwargs):
        (name,) = kwargs
        before = threading.active_count()
        with pytest.raises(ValueError, match=name):
            BetterstackSink(token="t", ingest_url=INGEST_URL, register_atexit=False, **kwargs)
        assert threading.active_count() == before  # rejected before any worker was started
