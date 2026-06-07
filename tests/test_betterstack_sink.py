"""Tests for the redesigned BetterstackSink: sync mode, batching, overflow, on_error."""

import json
import threading

import httpx
from pytest_httpx import HTTPXMock

from multilog import BetterstackSink, OverflowPolicy, QueueFull

INGEST_URL = "https://in.logs.example.com"


def _payload(message="hi", level="info"):
    return {"message": message, "level": level, "timestamp_ms": 1_700_000_000_000}


def _sync_sink(monkeypatch, **kwargs) -> BetterstackSink:
    """A synchronous (unbuffered) sink whose backoff sleeps are skipped."""
    sink = BetterstackSink(
        token="t", ingest_url=INGEST_URL, batch=False, register_atexit=False, **kwargs
    )
    monkeypatch.setattr(sink, "_sleep_backoff", lambda _attempt: None)
    return sink


# --------------------------------------------------------------------------
# Synchronous (batch=False) mode
# --------------------------------------------------------------------------


class TestSyncMode:
    def test_posts_to_ingest_url(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL, batch=False, register_atexit=False)

        sink._emit(_payload())

        requests = httpx_mock.get_requests()
        assert len(requests) == 1
        assert str(requests[0].url) == INGEST_URL
        sink.close()

    def test_sends_bearer_token_and_json_content_type(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = BetterstackSink(
            token="tok-xyz", ingest_url=INGEST_URL, batch=False, register_atexit=False
        )

        sink._emit(_payload())

        req = httpx_mock.get_requests()[0]
        assert req.headers["Authorization"] == "Bearer tok-xyz"
        assert req.headers["Content-Type"] == "application/json"
        sink.close()

    def test_body_is_json_array_of_events(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL, batch=False, register_atexit=False)
        payload = _payload(message="payload-test")

        sink._emit(payload)

        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body == [payload]
        sink.close()

    def test_no_worker_thread(self):
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL, batch=False, register_atexit=False)
        assert sink._worker is None
        sink.close()


class TestSyncRetry:
    def test_recovers_after_transient_5xx(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_response(url=INGEST_URL, status_code=503)
        httpx_mock.add_response(url=INGEST_URL, status_code=503)
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _sync_sink(monkeypatch, max_retries=3)

        sink._emit(_payload())

        assert len(httpx_mock.get_requests()) == 3
        sink.close()

    def test_retries_on_429(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_response(url=INGEST_URL, status_code=429)
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _sync_sink(monkeypatch, max_retries=3)

        sink._emit(_payload())

        assert len(httpx_mock.get_requests()) == 2
        sink.close()

    def test_retries_on_transport_error(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_exception(httpx.ConnectError("conn refused"))
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _sync_sink(monkeypatch, max_retries=3)

        sink._emit(_payload())

        assert len(httpx_mock.get_requests()) == 2
        sink.close()

    def test_max_retries_zero_means_one_attempt(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_response(url=INGEST_URL, status_code=503, is_reusable=True)
        errors: list = []
        sink = _sync_sink(monkeypatch, max_retries=0, on_error=lambda e, p: errors.append((e, p)))

        sink._emit(_payload())

        assert len(httpx_mock.get_requests()) == 1
        assert len(errors) == 1
        sink.close()

    def test_sleep_backoff_within_bound(self, monkeypatch):
        slept: list[float] = []
        monkeypatch.setattr("multilog.sinks.betterstack.time.sleep", slept.append)
        monkeypatch.setattr("multilog.sinks.betterstack.random.uniform", lambda _a, b: b)

        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            batch=False,
            register_atexit=False,
            backoff_base=0.5,
            backoff_max=8.0,
        )
        for attempt in range(4):
            sink._sleep_backoff(attempt)

        assert len(slept) == 4
        for attempt, duration in enumerate(slept):
            assert duration == min(8.0, 0.5 * (2**attempt))
        sink.close()


class TestNeverRaisesAndOnError:
    def test_terminal_5xx_calls_on_error_with_payloads(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_response(url=INGEST_URL, status_code=503, is_reusable=True)
        errors: list = []
        sink = _sync_sink(monkeypatch, max_retries=2, on_error=lambda e, p: errors.append((e, p)))

        payload = _payload("doomed")
        sink._emit(payload)  # must not raise

        assert len(httpx_mock.get_requests()) == 3
        assert len(errors) == 1
        exc, payloads = errors[0]
        assert isinstance(exc, httpx.HTTPStatusError)
        assert payloads == (payload,)
        sink.close()

    def test_4xx_fails_fast_and_calls_on_error(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_response(url=INGEST_URL, status_code=401)
        errors: list = []
        sink = _sync_sink(monkeypatch, max_retries=3, on_error=lambda e, p: errors.append((e, p)))

        sink._emit(_payload())

        assert len(httpx_mock.get_requests()) == 1  # no retry on 4xx
        assert len(errors) == 1
        assert isinstance(errors[0][0], httpx.HTTPStatusError)
        sink.close()

    def test_on_error_receives_transport_exception(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_exception(httpx.ReadTimeout("slow"), is_reusable=True)
        errors: list = []
        sink = _sync_sink(monkeypatch, max_retries=0, on_error=lambda e, p: errors.append((e, p)))

        sink._emit(_payload())

        assert isinstance(errors[0][0], httpx.TimeoutException)
        sink.close()

    def test_emit_never_raises_without_on_error(self, httpx_mock: HTTPXMock, monkeypatch, capsys):
        httpx_mock.add_exception(httpx.ConnectError("down"), is_reusable=True)
        sink = _sync_sink(monkeypatch, max_retries=1)  # no on_error

        sink._emit(_payload())  # must not raise

        assert "delivery failed" in capsys.readouterr().err
        sink.close()

    def test_unserializable_event_isolated(self, httpx_mock: HTTPXMock):
        errors: list = []
        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            batch=False,
            register_atexit=False,
            on_error=lambda e, p: errors.append((e, p)),
        )
        bad = {"message": "bad", (1, 2): "tuple-key-not-json"}

        sink._emit(bad)  # must not raise

        assert len(errors) == 1
        assert len(httpx_mock.get_requests()) == 0  # nothing serializable to send
        sink.close()


# --------------------------------------------------------------------------
# Batching (batch=True) mode
# --------------------------------------------------------------------------


class TestBatchMode:
    def test_starts_and_stops_worker(self):
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL, batch=True, register_atexit=False)
        assert sink._worker is not None
        assert sink._worker.is_alive()

        sink.close()
        assert not sink._worker.is_alive()

    def test_flushes_pending_events_on_close(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=202, is_reusable=True)
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL, batch=True, register_atexit=False)

        sink._emit(_payload("a"))
        sink._emit(_payload("b"))
        sink.close()

        delivered = []
        for req in httpx_mock.get_requests():
            body = json.loads(req.content)
            assert isinstance(body, list)  # always a JSON array
            delivered.extend(body)
        assert {e["message"] for e in delivered} == {"a", "b"}

    def test_close_is_idempotent(self):
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL, batch=True, register_atexit=False)
        sink.close()
        sink.close()  # must not raise
        assert sink._closed is True

    def test_close_from_on_error_does_not_deadlock(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=503, is_reusable=True)
        calls: list = []
        holder: dict = {}

        def on_err(exc, payloads):
            calls.append(exc)
            holder["sink"].close()  # runs on the worker thread -> must not self-join

        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            batch=True,
            max_retries=0,
            on_error=on_err,
            register_atexit=False,
            flush_timeout=2.0,
        )
        holder["sink"] = sink

        sink._emit(_payload())
        sink.close()  # flush from main thread

        assert len(calls) == 1


class TestOverflowPolicies:
    def _park_worker(self, sink, monkeypatch):
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

    def test_policy_accepts_string(self):
        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            batch=True,
            overflow_policy="buffer",
            register_atexit=False,
        )
        assert sink._overflow_policy is OverflowPolicy.BUFFER
        sink.close()

    def test_drop_reports_queue_full(self, monkeypatch):
        errors: list = []
        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            batch=True,
            queue_size=2,
            overflow_policy=OverflowPolicy.DROP,
            on_error=lambda e, p: errors.append((e, p)),
            register_atexit=False,
        )
        started, release = self._park_worker(sink, monkeypatch)

        sink._emit(_payload("A"))  # worker takes A and parks
        assert started.wait(2)
        sink._emit(_payload("B"))  # queue: [B]
        sink._emit(_payload("C"))  # queue: [B, C] -> full
        sink._emit(_payload("D"))  # overflow -> dropped

        assert len(errors) == 1
        exc, payloads = errors[0]
        assert isinstance(exc, QueueFull)
        assert payloads[0]["message"] == "D"

        release.set()
        sink.close()

    def test_buffer_holds_overflow(self, monkeypatch):
        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            batch=True,
            queue_size=2,
            overflow_policy=OverflowPolicy.BUFFER,
            register_atexit=False,
        )
        started, release = self._park_worker(sink, monkeypatch)

        sink._emit(_payload("A"))
        assert started.wait(2)
        sink._emit(_payload("B"))
        sink._emit(_payload("C"))
        sink._emit(_payload("D"))  # overflow -> buffered, not dropped

        assert sink._overflow is not None
        assert [p["message"] for p in sink._overflow] == ["D"]

        release.set()
        sink.close()

    def test_block_blocks_caller_until_space(self, monkeypatch):
        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            batch=True,
            queue_size=2,
            overflow_policy=OverflowPolicy.BLOCK,
            register_atexit=False,
        )
        started, release = self._park_worker(sink, monkeypatch)

        sink._emit(_payload("A"))
        assert started.wait(2)
        sink._emit(_payload("B"))
        sink._emit(_payload("C"))  # queue full

        producer = threading.Thread(target=lambda: sink._emit(_payload("D")))
        producer.start()
        producer.join(timeout=0.5)
        assert producer.is_alive()  # blocked: queue full

        release.set()  # worker drains the queue, freeing space
        producer.join(timeout=5)
        assert not producer.is_alive()

        sink.close()
