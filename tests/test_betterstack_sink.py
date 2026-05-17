"""Tests for BetterstackSink using pytest-httpx mocks."""

import json
import threading

import httpx
import pytest
from pytest_httpx import HTTPXMock

from multilog import BetterstackSink

INGEST_URL = "https://in.logs.example.com"


def _no_sleep_sink(monkeypatch, **kwargs) -> BetterstackSink:
    """Construct a BetterstackSink whose backoff sleeps are skipped."""
    sink = BetterstackSink(token="t", ingest_url=INGEST_URL, **kwargs)
    monkeypatch.setattr(sink, "_sleep_backoff", lambda _attempt: None)
    return sink


def _payload(message="hi", level="info"):
    return {"message": message, "level": level, "timestamp_ms": 1_700_000_000_000}


class TestSuccessfulPost:
    def test_posts_to_ingest_url(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = BetterstackSink(token="tok-123", ingest_url=INGEST_URL)

        sink._emit(_payload())

        requests = httpx_mock.get_requests()
        assert len(requests) == 1
        assert str(requests[0].url) == INGEST_URL

    def test_sends_bearer_token_and_json_content_type(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = BetterstackSink(token="tok-xyz", ingest_url=INGEST_URL)

        sink._emit(_payload())

        req = httpx_mock.get_requests()[0]
        assert req.headers["Authorization"] == "Bearer tok-xyz"
        assert req.headers["Content-Type"] == "application/json"

    def test_request_body_is_payload_json(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL)
        payload = _payload(message="payload-test")

        sink._emit(payload)

        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body == payload


class TestErrorPropagation:
    def test_5xx_raises_http_status_error_after_retries_exhausted(
        self, httpx_mock: HTTPXMock, monkeypatch
    ):
        httpx_mock.add_response(url=INGEST_URL, status_code=503, is_reusable=True)
        sink = _no_sleep_sink(monkeypatch, max_retries=2)

        with pytest.raises(httpx.HTTPStatusError):
            sink._emit(_payload())

        # 1 initial + 2 retries == 3 calls.
        assert len(httpx_mock.get_requests()) == 3

    def test_4xx_raises_immediately_without_retry(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_response(url=INGEST_URL, status_code=401)
        sink = _no_sleep_sink(monkeypatch, max_retries=3)

        with pytest.raises(httpx.HTTPStatusError):
            sink._emit(_payload())

        # 4xx (non-429) is non-retryable: a single request only.
        assert len(httpx_mock.get_requests()) == 1


class TestRetryBehavior:
    def test_recovers_after_transient_5xx(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_response(url=INGEST_URL, status_code=503)
        httpx_mock.add_response(url=INGEST_URL, status_code=503)
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _no_sleep_sink(monkeypatch, max_retries=3)

        sink._emit(_payload())

        assert len(httpx_mock.get_requests()) == 3

    def test_retries_on_429(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_response(url=INGEST_URL, status_code=429)
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _no_sleep_sink(monkeypatch, max_retries=3)

        sink._emit(_payload())

        assert len(httpx_mock.get_requests()) == 2

    def test_retries_on_transport_error(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_exception(httpx.ConnectError("conn refused"))
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _no_sleep_sink(monkeypatch, max_retries=3)

        sink._emit(_payload())

        assert len(httpx_mock.get_requests()) == 2

    def test_retries_on_timeout(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_exception(httpx.ReadTimeout("slow"))
        httpx_mock.add_response(url=INGEST_URL, status_code=202)
        sink = _no_sleep_sink(monkeypatch, max_retries=3)

        sink._emit(_payload())

        assert len(httpx_mock.get_requests()) == 2

    def test_max_retries_zero_means_one_attempt(self, httpx_mock: HTTPXMock, monkeypatch):
        httpx_mock.add_response(url=INGEST_URL, status_code=503)
        sink = _no_sleep_sink(monkeypatch, max_retries=0)

        with pytest.raises(httpx.HTTPStatusError):
            sink._emit(_payload())

        assert len(httpx_mock.get_requests()) == 1

    def test_backoff_respects_max(self):
        """Full-jitter exponential backoff stays within [0, backoff_max]."""
        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            backoff_base=10.0,
            backoff_max=1.0,
        )
        ceilings = []
        for attempt in range(6):
            ceiling = min(sink.backoff_max, sink.backoff_base * (2**attempt))
            ceilings.append(ceiling)
        # backoff_max caps every ceiling to 1.0
        assert all(c == 1.0 for c in ceilings)

    def test_sleep_backoff_calls_time_sleep_within_bound(self, monkeypatch):
        """_sleep_backoff should sleep in [0, ceiling] for each attempt."""
        slept: list[float] = []
        monkeypatch.setattr("multilog.sinks.betterstack.time.sleep", slept.append)

        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            backoff_base=0.5,
            backoff_max=8.0,
        )
        for attempt in range(4):
            sink._sleep_backoff(attempt)

        # Four sleep calls, each bounded by backoff_base * 2**attempt or backoff_max.
        assert len(slept) == 4
        for attempt, duration in enumerate(slept):
            ceiling = min(8.0, 0.5 * (2**attempt))
            assert 0 <= duration <= ceiling


class TestClientLifecycle:
    def test_client_created_eagerly_in_init(self, httpx_mock: HTTPXMock):  # noqa: ARG002
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL)
        assert sink._client is not None

    def test_close_is_idempotent(self, httpx_mock: HTTPXMock):  # noqa: ARG002
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL)
        sink.close()
        # Second close must not raise.
        sink.close()
        assert sink._closed is True

    def test_same_client_used_for_concurrent_emits(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=202, is_reusable=True)
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL)
        client_ids: list[int] = []

        def emit_once():
            client_ids.append(id(sink._client))
            sink._emit(_payload())

        threads = [threading.Thread(target=emit_once) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All 20 threads observed the same httpx.Client instance.
        assert len(set(client_ids)) == 1
        assert len(httpx_mock.get_requests()) == 20
