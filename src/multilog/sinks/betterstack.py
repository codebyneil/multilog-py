"""Betterstack sink for multilog-py."""

import random
import time
from typing import Any

import httpx

from multilog.levels import LogLevel
from multilog.sinks.base import BaseSink

_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


class BetterstackSink(BaseSink):
    """Sink for sending logs to Betterstack."""

    def __init__(
        self,
        token: str,
        ingest_url: str,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        backoff_max: float = 8.0,
        default_context: dict[str, Any] | None = None,
        included_levels: list[LogLevel] | None = None,
    ):
        """
        Initialize Betterstack sink.

        Transient failures (httpx transport/timeout errors, HTTP 408/429,
        and HTTP 5xx) are retried up to ``max_retries`` times with full-jitter
        exponential backoff. Other 4xx responses fail fast.

        Args:
            token: Betterstack authentication token.
            ingest_url: Betterstack ingest URL.
            timeout: HTTP request timeout in seconds.
            max_retries: Number of retry attempts after the first failed POST.
                ``0`` disables retries.
            backoff_base: Base for the exponential backoff in seconds.
            backoff_max: Upper bound on a single backoff sleep in seconds.
            default_context: Default context merged into all log entries from this sink.
            included_levels: Log levels this sink will emit. Defaults to all levels.
        """
        super().__init__(default_context=default_context, included_levels=included_levels)
        self.token = token
        self.ingest_url = ingest_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self._client = httpx.Client(timeout=timeout)
        self._closed = False

    def _emit(self, payload: dict[str, Any]) -> None:
        """Send log to Betterstack via HTTP POST with retry on transient failure."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.post(self.ingest_url, headers=headers, json=payload)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
            else:
                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                    return
                # Retryable status — surface the HTTPStatusError on the last attempt.
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    last_exc = exc

            if attempt < self.max_retries:
                self._sleep_backoff(attempt)

        assert last_exc is not None
        raise last_exc

    def _sleep_backoff(self, attempt: int) -> None:
        """Sleep with full-jitter exponential backoff for the given retry attempt."""
        ceiling = min(self.backoff_max, self.backoff_base * (2**attempt))
        time.sleep(random.uniform(0, ceiling))

    def close(self) -> None:
        """Close the HTTP client."""
        if not self._closed:
            self._client.close()
            self._closed = True
