"""Tests for BetterstackSink using pytest-httpx mocks."""

import json
import threading

import httpx
import pytest
from pytest_httpx import HTTPXMock

from multilog import BetterstackSink

INGEST_URL = "https://in.logs.example.com"


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
    def test_5xx_raises_http_status_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=503)
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL)

        with pytest.raises(httpx.HTTPStatusError):
            sink._emit(_payload())

    def test_4xx_raises_http_status_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INGEST_URL, status_code=401)
        sink = BetterstackSink(token="t", ingest_url=INGEST_URL)

        with pytest.raises(httpx.HTTPStatusError):
            sink._emit(_payload())


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
