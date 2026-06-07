"""Tests for the 1.1 BetterstackSink features: dt event-time, Retry-After, flush()."""

import json
import threading
import time
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
from pytest_httpx import HTTPXMock

from multilog import BetterstackSink
from multilog.sinks.betterstack import _iso_ms

INGEST_URL = "https://in.logs.example.com"


def _payload(message="hi", **extra):
    return {"message": message, "level": "info", "timestamp_ms": 1_700_000_000_000, **extra}


def _events(httpx_mock: HTTPXMock):
    events = []
    for req in httpx_mock.get_requests():
        events.extend(json.loads(req.content))
    return events


def _sink(**kwargs) -> BetterstackSink:
    return BetterstackSink(token="t", ingest_url=INGEST_URL, register_atexit=False, **kwargs)


# --------------------------------------------------------------------------
# Event-time dt
# --------------------------------------------------------------------------


class TestEventTimeDt:
    def test_iso_ms_format(self):
        assert _iso_ms(1_700_000_000_000) == "2023-11-14T22:13:20.000Z"
        assert _iso_ms(1_700_000_000_123) == "2023-11-14T22:13:20.123Z"

    def test_dt_added_from_timestamp_ms(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _sink(batch=False)
        sink._emit(_payload())
        event = _events(httpx_mock)[0]
        assert event["dt"] == "2023-11-14T22:13:20.000Z"
        assert event["timestamp_ms"] == 1_700_000_000_000  # original kept too
        sink.close()

    def test_user_supplied_dt_is_preserved(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _sink(batch=False)
        sink._emit(_payload(dt="2020-01-01T00:00:00.000Z"))
        assert _events(httpx_mock)[0]["dt"] == "2020-01-01T00:00:00.000Z"
        sink.close()

    def test_missing_timestamp_ms_omits_dt(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _sink(batch=False)
        sink._emit({"message": "m", "level": "info"})  # no timestamp_ms
        assert "dt" not in _events(httpx_mock)[0]
        sink.close()


# --------------------------------------------------------------------------
# Retry-After
# --------------------------------------------------------------------------


class TestRetryAfter:
    def test_parses_header_variants(self):
        sink = _sink(batch=False)
        assert sink._retry_after_seconds(httpx.Response(429)) is None
        assert sink._retry_after_seconds(httpx.Response(429, headers={"Retry-After": "x"})) is None
        assert sink._retry_after_seconds(httpx.Response(429, headers={"Retry-After": "3"})) == 3.0
        sink.close()

    def test_naive_http_date_is_treated_as_utc(self):
        sink = _sink(batch=False)
        # "-0000" yields a naive datetime (unknown zone); the sink assumes UTC.
        secs = sink._retry_after_seconds(
            httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2099 07:28:00 -0000"})
        )
        assert secs is not None and secs > 0
        sink.close()

    def test_honors_retry_after_seconds(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_response(url=INGEST_URL, status_code=429, headers={"Retry-After": "2"})
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _sink(batch=False, max_retries=3)
        slept: list[float] = []
        monkeypatch.setattr(sink, "_sleep", slept.append)

        sink._emit(_payload())

        assert slept == [2.0]  # honored Retry-After, not jittered backoff
        sink.close()

    def test_honors_retry_after_http_date(self, httpx_mock: HTTPXMock, monkeypatch):
        future = datetime.now(UTC) + timedelta(seconds=5)
        httpx_mock.add_response(
            url=INGEST_URL, status_code=429, headers={"Retry-After": format_datetime(future)}
        )
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _sink(batch=False, max_retries=3)
        slept: list[float] = []
        monkeypatch.setattr(sink, "_sleep", slept.append)

        sink._emit(_payload())

        assert len(slept) == 1
        assert 0 < slept[0] <= 6  # ~5s from now
        sink.close()

    def test_falls_back_to_backoff_without_header(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_response(url=INGEST_URL, status_code=503)  # no Retry-After
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _sink(batch=False, max_retries=3)
        counts = {"sleep": 0, "backoff": 0}
        monkeypatch.setattr(
            sink, "_sleep", lambda _d: counts.__setitem__("sleep", counts["sleep"] + 1)
        )
        monkeypatch.setattr(
            sink, "_sleep_backoff", lambda _a: counts.__setitem__("backoff", counts["backoff"] + 1)
        )

        sink._emit(_payload())

        assert counts == {"sleep": 0, "backoff": 1}
        sink.close()


# --------------------------------------------------------------------------
# flush()
# --------------------------------------------------------------------------


class TestFlush:
    def test_flush_delivers_pending_and_keeps_sink_usable(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=202, is_reusable=True)
        # Long flush_interval so only flush() forces delivery.
        sink = _sink(batch=True, flush_interval=30.0)

        sink._emit(_payload("a"))
        sink._emit(_payload("b"))
        assert sink.flush(timeout=5) is True

        assert {e["message"] for e in _events(httpx_mock)} == {"a", "b"}
        assert sink._queue is not None and sink._queue.empty()

        # Sink remains usable after flush.
        sink._emit(_payload("c"))
        assert sink.flush(timeout=5) is True
        assert "c" in {e["message"] for e in _events(httpx_mock)}
        sink.close()

    def test_flush_is_noop_in_sync_mode(self):
        sink = _sink(batch=False)
        assert sink.flush() is True
        sink.close()

    def test_flush_is_noop_after_close(self):
        sink = _sink(batch=True)
        sink.close()
        assert sink.flush() is True

    def test_flush_from_worker_thread_returns_true(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=503, is_reusable=True)
        results: list = []
        holder: dict = {}

        def on_err(_exc, _payloads):
            results.append(holder["sink"].flush())  # runs on the worker thread, sink still open

        sink = _sink(batch=True, max_retries=0, on_error=on_err, flush_interval=0.02)
        holder["sink"] = sink
        sink._emit(_payload())

        deadline = time.monotonic() + 3
        while not results and time.monotonic() < deadline:
            time.sleep(0.01)

        assert results == [True]  # returned via the worker-thread guard, no self-deadlock
        sink.close()

    def test_flush_times_out_when_worker_stuck(self, monkeypatch):
        sink = _sink(batch=True)
        started = threading.Event()
        release = threading.Event()
        calls: list = []

        def blocking_send(payloads):
            calls.append(list(payloads))
            if len(calls) == 1:
                started.set()
                release.wait(timeout=5)

        monkeypatch.setattr(sink, "_send", blocking_send)

        sink._emit(_payload("A"))  # worker grabs A and parks in _send
        assert started.wait(2)
        sink._emit(_payload("B"))  # queued behind the parked send

        assert sink.flush(timeout=0.1) is False  # cannot drain while worker is stuck

        release.set()
        sink.close()

    def test_flush_on_idle_sink_returns_true(self):
        sink = _sink(batch=True, flush_interval=0.02)
        # Nothing queued and no HTTP call: the worker's blocking get returns the
        # flush marker first and sets its event.
        assert sink.flush(timeout=5) is True
        sink.close()

    def test_flush_marker_signaled_at_shutdown(self, monkeypatch):
        sink = _sink(batch=True, flush_interval=0.02)
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

        flush_result: list = []
        waiter = threading.Thread(target=lambda: flush_result.append(sink.flush(timeout=5)))
        waiter.start()
        time.sleep(0.1)  # let the marker land in the queue behind the parked worker

        sink.close(flush_timeout=0.1)  # worker still parked -> shutdown drains the marker
        release.set()
        waiter.join(timeout=5)

        assert flush_result == [True]  # shutdown set the marker's event
