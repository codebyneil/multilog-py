"""Betterstack sink for multilog-py.

Robust by default: ``batch=True`` (the default) hands each event to a background
worker thread that POSTs events in batches, so the calling thread is never
blocked on network I/O. Delivery failures are surfaced through an ``on_error``
callback instead of vanishing to stderr. ``batch=False`` is a synchronous,
unbuffered mode that POSTs one event per call — the right choice for a
short-lived CLI where a background thread would never get to flush.

A sink never raises into the caller: every failure path is routed to
``on_error`` (or stderr if none is set).
"""

from __future__ import annotations

import atexit
import contextlib
import json
import queue
import random
import sys
import threading
import time
import traceback
from collections import deque
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from enum import StrEnum
from typing import Any

import httpx

from multilog.exceptions import QueueFull
from multilog.levels import LogLevel
from multilog.sinks.base import BaseSink

_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})

# Sentinel pushed onto the queue by close() to wake and stop the worker.
_STOP = object()


class _FlushMarker:
    """Queue marker whose event is set once all events enqueued before it ship."""

    __slots__ = ("event",)

    def __init__(self) -> None:
        self.event = threading.Event()


def _iso_ms(ms: int) -> str:
    """Render epoch milliseconds as a Betterstack-friendly ISO 8601 UTC string."""
    dt = datetime.fromtimestamp(ms / 1000, tz=UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


OnError = Callable[[Exception, "tuple[dict[str, Any], ...]"], None]


class OverflowPolicy(StrEnum):
    """How a batching ``BetterstackSink`` behaves when its queue is full.

    - ``DROP`` (default): drop the new event and report it via ``on_error``
      with a :class:`~multilog.exceptions.QueueFull` exception. The caller is
      never blocked. Best for long-running services where losing a log line
      beats stalling a request.
    - ``BUFFER``: move overflow into an unbounded in-memory buffer that the
      worker drains when the queue drains. Preserves delivery at the cost of
      unbounded memory if the destination stays down — use for batch jobs.
    - ``BLOCK``: block the caller until the queue has room. Provides
      backpressure but can hang the calling thread if the destination is
      down. Dangerous; use only when you would rather stall than lose a log.
    """

    DROP = "drop"
    BUFFER = "buffer"
    BLOCK = "block"


class BetterstackSink(BaseSink):
    """Sink for sending logs to Betterstack."""

    def __init__(
        self,
        token: str,
        ingest_url: str,
        *,
        batch: bool = True,
        batch_size: int = 100,
        flush_interval: float = 1.0,
        queue_size: int = 10_000,
        overflow_policy: OverflowPolicy | str = OverflowPolicy.DROP,
        on_error: OnError | None = None,
        register_atexit: bool = True,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        backoff_max: float = 8.0,
        flush_timeout: float = 5.0,
        min_level: LogLevel = LogLevel.TRACE,
        only: Iterable[LogLevel] | None = None,
    ):
        """Initialize the Betterstack sink.

        Transient failures (httpx transport/timeout errors, HTTP 408/429, and
        HTTP 5xx) are retried up to ``max_retries`` times with full-jitter
        exponential backoff. Other 4xx responses fail fast. On terminal
        failure the affected events are passed to ``on_error``.

        Args:
            token: Betterstack source token.
            ingest_url: Betterstack ingest URL.
            batch: When True (default), enqueue events and deliver them from a
                background worker thread in batches. When False, POST each
                event synchronously on the calling thread.
            batch_size: Max events per POST in batch mode.
            flush_interval: Max seconds the worker waits before flushing a
                partial batch.
            queue_size: Capacity of the in-memory queue in batch mode.
            overflow_policy: What to do when the queue is full. See
                :class:`OverflowPolicy`.
            on_error: Called as ``on_error(exception, payloads)`` when delivery
                fails terminally, when an event is dropped, or when events
                remain undelivered at close. ``payloads`` is a tuple of the
                affected log dicts. Runs on the worker thread (or the calling
                thread for overflow drops); it must not raise and should be
                fast. If None, failures are printed to stderr.
            register_atexit: When True (default) and ``batch`` is True, register
                an ``atexit`` hook that flushes on interpreter shutdown so
                events are not silently lost when ``close()`` is never called.
            timeout: Per-request HTTP timeout in seconds.
            max_retries: Retry attempts after the first failed POST. ``0``
                disables retries.
            backoff_base: Base for exponential backoff, in seconds.
            backoff_max: Upper bound on a single backoff sleep, in seconds.
            flush_timeout: Total seconds ``close()`` waits to drain pending
                events before reporting the remainder via ``on_error``.
            min_level: Emit entries at this severity or higher.
            only: Explicit set of levels to emit (overrides ``min_level``).
        """
        super().__init__(min_level=min_level, only=only)
        self.token = token
        self.ingest_url = ingest_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.flush_timeout = flush_timeout

        self._batch = batch
        self._batch_size = max(1, batch_size)
        self._flush_interval = flush_interval
        self._queue_size = queue_size
        self._overflow_policy = OverflowPolicy(overflow_policy)
        self._on_error = on_error

        self._client = httpx.Client(timeout=timeout)
        self._closed = False
        self._close_lock = threading.Lock()
        # Deadline for bounding retry/backoff during shutdown; None otherwise.
        self._deadline: float | None = None

        self._queue: queue.Queue[Any] | None = None
        self._overflow: deque[dict[str, Any]] | None = None
        self._overflow_lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._atexit_registered = False

        if self._batch:
            self._queue = queue.Queue(maxsize=queue_size)
            if self._overflow_policy is OverflowPolicy.BUFFER:
                self._overflow = deque()
            self._worker = threading.Thread(
                target=self._worker_loop,
                name=f"BetterstackSink-worker-{id(self)}",
                daemon=True,
            )
            self._worker.start()
            if register_atexit:
                atexit.register(self._atexit_close)
                self._atexit_registered = True

    # -- emit -------------------------------------------------------------

    def _emit(self, payload: dict[str, Any]) -> None:
        """Queue (batch mode) or POST (sync mode) one event. Never raises."""
        if self._batch:
            self._enqueue(payload)
        else:
            self._send([payload])

    def _enqueue(self, payload: dict[str, Any]) -> None:
        if self._closed:
            return
        assert self._queue is not None
        try:
            self._queue.put_nowait(payload)
            return
        except queue.Full:
            pass

        if self._overflow_policy is OverflowPolicy.DROP:
            self._handle_error(
                QueueFull(f"BetterstackSink queue full (size={self._queue_size}); dropped 1 event"),
                (payload,),
            )
        elif self._overflow_policy is OverflowPolicy.BUFFER:
            assert self._overflow is not None
            with self._overflow_lock:
                self._overflow.append(payload)
        else:  # BLOCK — may hang if the destination is down (documented footgun)
            with contextlib.suppress(Exception):  # pragma: no cover - defensive
                self._queue.put(payload)

    # -- worker -----------------------------------------------------------

    def _worker_loop(self) -> None:
        stopping = False
        try:
            while True:
                batch, stop, flush_marker = self._collect_batch(block=not stopping)
                if stop:
                    stopping = True
                if batch:
                    self._send(batch)
                if flush_marker is not None:
                    # Everything enqueued before the marker has now shipped.
                    flush_marker.event.set()
                if not batch and flush_marker is None and stopping:
                    break
        except Exception:  # pragma: no cover - defense in depth; must not die silently
            traceback.print_exc(file=sys.stderr)

    def _collect_batch(
        self, *, block: bool
    ) -> tuple[list[dict[str, Any]], bool, _FlushMarker | None]:
        """Gather up to ``batch_size`` events from the queue and overflow buffer.

        Returns the batch, whether the stop sentinel was seen, and a flush marker
        if one was reached (collection stops at a marker so the items before it
        ship before the marker's event is set).
        """
        assert self._queue is not None
        batch: list[dict[str, Any]] = []
        stop = False
        flush_marker: _FlushMarker | None = None

        if block:
            try:
                first = self._queue.get(timeout=self._flush_interval)
            except queue.Empty:
                first = None
            if first is _STOP:
                stop = True
            elif isinstance(first, _FlushMarker):
                flush_marker = first
            elif first is not None:
                batch.append(first)

        if not stop and flush_marker is None:
            while len(batch) < self._batch_size:
                try:
                    item = self._queue.get_nowait()
                except queue.Empty:
                    break
                if item is _STOP:
                    stop = True
                    break
                if isinstance(item, _FlushMarker):
                    flush_marker = item
                    break
                batch.append(item)

        if flush_marker is None and self._overflow is not None and len(batch) < self._batch_size:
            with self._overflow_lock:
                while self._overflow and len(batch) < self._batch_size:
                    batch.append(self._overflow.popleft())

        return batch, stop, flush_marker

    def flush(self, timeout: float | None = None) -> bool:
        """Block until events queued so far are delivered.

        Returns ``True`` once the queue has drained (or there was nothing to
        flush), ``False`` if ``timeout`` elapsed first. A no-op that returns
        ``True`` in synchronous mode, after ``close()``, or when called from the
        worker thread (e.g. inside ``on_error``) to avoid self-deadlock.
        """
        if not self._batch or self._closed:
            return True
        if self._worker is not None and threading.current_thread() is self._worker:
            return True
        assert self._queue is not None
        marker = _FlushMarker()
        self._queue.put(marker)
        return marker.event.wait(timeout)

    # -- delivery ---------------------------------------------------------

    def _send(self, payloads: list[dict[str, Any]]) -> None:
        """POST a batch with retries. Routes terminal failures to on_error. Never raises."""
        body, good = self._serialize(payloads)
        if body is None:
            return

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        data = body.encode("utf-8")
        last_exc: Exception | None = None

        for attempt in range(self.max_retries + 1):
            if self._deadline is not None and time.monotonic() >= self._deadline:
                break
            retry_after: float | None = None
            try:
                response = self._client.post(self.ingest_url, headers=headers, content=data)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
            else:
                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        self._handle_error(exc, tuple(good))
                    return
                retry_after = self._retry_after_seconds(response)
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    last_exc = exc

            if attempt < self.max_retries:
                if retry_after is not None:
                    self._sleep(retry_after)
                else:
                    self._sleep_backoff(attempt)

        if last_exc is not None:
            self._handle_error(last_exc, tuple(good))

    def _serialize(self, payloads: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
        """Serialize a batch to a JSON array, isolating any unserializable event."""
        parts: list[str] = []
        good: list[dict[str, Any]] = []
        for payload in payloads:
            try:
                parts.append(json.dumps(self._betterstack_event(payload), default=str))
            except Exception as exc:  # one bad event must not sink the whole batch
                self._handle_error(exc, (payload,))
                continue
            good.append(payload)
        if not parts:
            return None, []
        return "[" + ",".join(parts) + "]", good

    @staticmethod
    def _betterstack_event(payload: dict[str, Any]) -> dict[str, Any]:
        """Augment a payload with an ISO ``dt`` event-time Betterstack understands.

        Without ``dt`` Betterstack stamps events with ingestion time, which drifts
        from the real event time once batching/retries delay delivery. A
        user-supplied ``dt`` is left untouched.
        """
        ts = payload.get("timestamp_ms")
        if "dt" in payload or not isinstance(ts, int):
            return payload
        return {**payload, "dt": _iso_ms(ts)}

    def _sleep_backoff(self, attempt: int) -> None:
        """Sleep with full-jitter exponential backoff, bounded by the shutdown deadline."""
        ceiling = min(self.backoff_max, self.backoff_base * (2**attempt))
        self._sleep(random.uniform(0, ceiling))

    def _sleep(self, delay: float) -> None:
        """Sleep ``delay`` seconds, clamped to the shutdown deadline when closing."""
        if self._deadline is not None:
            delay = min(delay, max(0.0, self._deadline - time.monotonic()))
        if delay > 0:
            time.sleep(delay)

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        """Parse a ``Retry-After`` header (delta-seconds or HTTP-date) into seconds."""
        value = response.headers.get("Retry-After")
        if not value:
            return None
        value = value.strip()
        try:
            return max(0.0, float(value))
        except ValueError:
            pass
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if when is None:  # pragma: no cover - parsedate_to_datetime raises on bad input in 3.11+
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        return max(0.0, when.timestamp() - time.time())

    def _handle_error(self, exc: Exception, payloads: tuple[dict[str, Any], ...]) -> None:
        if self._on_error is not None:
            try:
                self._on_error(exc, payloads)
            except Exception:
                traceback.print_exc(file=sys.stderr)
        else:
            print(
                f"BetterstackSink delivery failed "
                f"({type(exc).__name__}: {exc}); {len(payloads)} event(s) lost",
                file=sys.stderr,
            )

    # -- shutdown ---------------------------------------------------------

    def close(self, *, flush_timeout: float | None = None) -> None:
        """Flush pending events and release resources. Idempotent. Never raises.

        Signals the worker to stop, drains pending events for up to
        ``flush_timeout`` seconds (falling back to the instance default), then
        reports any still-undelivered events via ``on_error`` and closes the
        HTTP client.
        """
        # Calling close() from within on_error (which runs on the worker thread)
        # would self-join and deadlock; the worker stops on its own anyway.
        if self._worker is not None and threading.current_thread() is self._worker:
            return

        with self._close_lock:
            if self._closed:
                return
            self._closed = True

        if not self._batch:
            self._client.close()
            return

        assert self._queue is not None and self._worker is not None
        timeout = self.flush_timeout if flush_timeout is None else flush_timeout
        self._deadline = time.monotonic() + timeout
        self._queue.put(_STOP)
        self._worker.join(timeout=timeout)
        self._report_unflushed()
        self._client.close()

        if self._atexit_registered:
            atexit.unregister(self._atexit_close)
            self._atexit_registered = False

    def _report_unflushed(self) -> None:
        """Report any events left in the queue/overflow after the drain deadline."""
        assert self._queue is not None
        pending: list[dict[str, Any]] = []
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is _STOP:
                continue
            if isinstance(item, _FlushMarker):
                item.event.set()  # never leave a flush() waiter hanging
                continue
            pending.append(item)
        if self._overflow is not None:
            with self._overflow_lock:
                pending.extend(self._overflow)
                self._overflow.clear()
        if pending:
            self._handle_error(
                TimeoutError(f"{len(pending)} event(s) undelivered at close"),
                tuple(pending),
            )

    def _atexit_close(self) -> None:
        with contextlib.suppress(Exception):  # pragma: no cover - atexit must never raise
            self.close(flush_timeout=2.0)
