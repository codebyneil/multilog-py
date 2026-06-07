"""Thread-safety / stress tests for the registry, state mutation, and sinks."""

import threading

from conftest import RecordingSink
from pytest_httpx import HTTPXMock

from multilog import (
    BetterstackSink,
    LogLevel,
    configure,
    get_async_logger,
    get_logger,
)

INGEST_URL = "https://in.logs.example.com"


def _run_threads(target, n):
    barrier = threading.Barrier(n)

    def wrapped(*args):
        barrier.wait()  # maximize contention by starting together
        target(*args)

    threads = [threading.Thread(target=wrapped, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


class TestRegistryThreadSafety:
    def test_concurrent_get_logger_returns_one_object(self):
        results: list = []
        lock = threading.Lock()

        def grab(_i):
            obj = get_logger("contended")
            with lock:
                results.append(obj)

        _run_threads(grab, 50)

        assert len(results) == 50
        assert len({id(o) for o in results}) == 1  # exactly one object

    def test_concurrent_get_logger_and_get_async_logger_share_state(self):
        sync_states: list = []
        async_states: list = []
        lock = threading.Lock()

        def grab(i):
            obj = get_logger("shared") if i % 2 == 0 else get_async_logger("shared")
            with lock:
                (sync_states if i % 2 == 0 else async_states).append(obj._state)

        _run_threads(grab, 40)

        all_states = {id(s) for s in sync_states + async_states}
        assert len(all_states) == 1  # sync and async share one state object


class TestStateMutationUnderDispatch:
    def test_stable_sink_receives_all_logs_while_sinks_churn(self):
        """A sink that is never removed receives every log, even while other
        sinks are concurrently added and removed."""
        base = RecordingSink()
        log = get_logger("churn")
        configure(sinks=[base], name="churn")

        n_loggers = 8
        per_thread = 200
        stop = threading.Event()

        def churn():
            while not stop.is_set():
                temp = RecordingSink()
                log.add_sink(temp)
                log.remove_sink(temp)

        def spam(_i):
            for _ in range(per_thread):
                log.log("x", LogLevel.INFO)

        churner = threading.Thread(target=churn)
        churner.start()
        try:
            _run_threads(spam, n_loggers)
        finally:
            stop.set()
            churner.join()

        assert len(base.payloads) == n_loggers * per_thread

    def test_set_sinks_racing_with_logging_never_raises(self):
        log = get_logger("race")
        configure(sinks=[RecordingSink()], name="race")
        stop = threading.Event()
        failures: list = []

        def swap():
            while not stop.is_set():
                try:
                    log.set_sinks([RecordingSink(), RecordingSink()])
                except Exception as exc:  # pragma: no cover - must never happen
                    failures.append(exc)

        def spam(_i):
            for _ in range(300):
                try:
                    log.log("x", LogLevel.INFO)
                except Exception as exc:  # pragma: no cover - must never happen
                    failures.append(exc)

        swapper = threading.Thread(target=swap)
        swapper.start()
        try:
            _run_threads(spam, 8)
        finally:
            stop.set()
            swapper.join()

        assert failures == []


class TestBetterstackConcurrentEnqueue:
    def test_no_events_lost_under_concurrent_enqueue(self, httpx_mock: HTTPXMock):
        import json

        httpx_mock.add_response(url=INGEST_URL, status_code=202, is_reusable=True)
        sink = BetterstackSink(
            token="t",
            ingest_url=INGEST_URL,
            batch=True,
            batch_size=50,
            flush_interval=0.02,
            register_atexit=False,
        )

        n_threads = 10
        per_thread = 100

        def emit_many(tid):
            for i in range(per_thread):
                sink._emit({"message": "e", "level": "info", "tid": tid, "i": i})

        _run_threads(emit_many, n_threads)
        sink.close()  # flush

        delivered = []
        for req in httpx_mock.get_requests():
            delivered.extend(json.loads(req.content))
        assert len(delivered) == n_threads * per_thread
        seen = {(e["tid"], e["i"]) for e in delivered}
        assert seen == {(t, i) for t in range(n_threads) for i in range(per_thread)}


class TestResourceCleanup:
    def test_closing_sinks_leaves_no_worker_threads(self):
        """Every batching sink's worker thread is gone after close() — no leaks."""
        sinks = [
            BetterstackSink(token="t", ingest_url=INGEST_URL, batch=True, register_atexit=False)
            for _ in range(20)
        ]
        workers = [s._worker for s in sinks]
        assert all(w is not None and w.is_alive() for w in workers)

        for s in sinks:
            s.close()

        assert all(not w.is_alive() for w in workers)
