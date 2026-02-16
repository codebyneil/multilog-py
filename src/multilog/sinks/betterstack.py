"""Betterstack sink for multilog-py."""

from typing import Any

import httpx

from multilog.levels import LogLevel
from multilog.sinks.base import BaseSink


class BetterstackSink(BaseSink):
    """Sink for sending logs to Betterstack."""

    def __init__(
        self,
        token: str,
        ingest_url: str,
        timeout: float = 10.0,
        default_context: dict[str, Any] | None = None,
        included_levels: list[LogLevel] | None = None,
    ):
        """
        Initialize Betterstack sink.

        Args:
            token: Betterstack authentication token
            ingest_url: Betterstack ingest URL
            timeout: HTTP request timeout in seconds
            default_context: Default context merged into all log entries from this sink.
            included_levels: Log levels this sink will emit. Defaults to all levels.
        """
        super().__init__(default_context=default_context, included_levels=included_levels)
        self.token = token
        self.ingest_url = ingest_url
        self.timeout = timeout
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        """
        Lazy initialize HTTP client.

        Returns:
            httpx.Client instance
        """
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def _emit(self, payload: dict[str, Any]) -> None:
        """
        Send log to Betterstack via HTTP POST.

        Args:
            payload: Log payload to send
        """
        client = self._get_client()

        response = client.post(
            self.ingest_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None
