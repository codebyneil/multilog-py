"""Live integration tests against a real Betterstack source.

Gated on credentials: reads BETTERSTACK_TOKEN / BETTERSTACK_INGEST_URL from the
environment, falling back to the repo-root .env. If neither is available the
whole module is skipped, so CI without secrets stays green.

"No on_error fired" is the in-test success signal — Betterstack returns 2xx on
accept, and any non-2xx or transport failure would invoke on_error.
"""

import os
import time
import uuid
from pathlib import Path

import pytest

from multilog import BetterstackSink, LogLevel, configure, get_logger


def _load_creds():
    token = os.environ.get("BETTERSTACK_TOKEN")
    url = os.environ.get("BETTERSTACK_INGEST_URL")
    if token and url:
        return token, url
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        values = {}
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()
        token = token or values.get("BETTERSTACK_TOKEN")
        url = url or values.get("BETTERSTACK_INGEST_URL")
    if token and url:
        return token, url
    return None


_CREDS = _load_creds()

pytestmark = pytest.mark.skipif(
    _CREDS is None,
    reason="set BETTERSTACK_TOKEN and BETTERSTACK_INGEST_URL (or repo .env) to run live tests",
)


@pytest.fixture
def errors():
    return []


@pytest.fixture
def run_id():
    return f"itest-{uuid.uuid4().hex[:8]}"


def _sink(errors, **kwargs):
    token, url = _CREDS
    return BetterstackSink(
        token, url, on_error=lambda e, p: errors.append((e, p)), register_atexit=False, **kwargs
    )


class TestLiveDelivery:
    def test_batch_delivery_no_errors(self, errors, run_id):
        configure(sinks=[_sink(errors, batch=True, flush_interval=0.5)], name="itest")
        log = get_logger("itest")
        for i in range(3):
            log.log("integration batch", LogLevel.INFO, {"run_id": run_id, "i": i})
        log.close()  # flush
        assert errors == []

    def test_sync_delivery_no_errors_and_returns(self, errors, run_id):
        sink = _sink(errors, batch=False)
        t0 = time.monotonic()
        sink._emit(
            {
                "message": "integration sync",
                "level": "warn",
                "timestamp_ms": int(time.time() * 1000),
                "run_id": run_id,
            }
        )
        elapsed = time.monotonic() - t0
        sink.close()
        assert errors == []
        assert elapsed < 10  # a single accepted POST should be quick

    def test_bind_and_log_exception_deliver(self, errors, run_id):
        configure(sinks=[_sink(errors, batch=True, flush_interval=0.5)], name="itest")
        log = get_logger("itest").bind(run_id=run_id, component="integration")
        log.log("bound integration event", LogLevel.INFO)
        try:
            raise ValueError("integration boom")
        except ValueError as exc:
            log.log_exception("integration exception", exc, level=LogLevel.ERROR)
        get_logger("itest").close()
        assert errors == []
