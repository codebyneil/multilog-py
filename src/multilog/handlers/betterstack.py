"""Betterstack handler for multilog-py."""

from typing import TYPE_CHECKING, Any

import httpx

from multilog.handlers.base import BaseHandler
from multilog.levels import LogLevel

if TYPE_CHECKING:
    from multilog.config import Config


class BetterstackHandler(BaseHandler):
    """Handler for sending logs to Betterstack."""

    def __init__(
        self,
        token: str,
        ingest_url: str,
        level: LogLevel = LogLevel.DEBUG,
        timeout: float = 10.0,
    ):
        """
        Initialize Betterstack handler.

        Args:
            token: Betterstack authentication token
            ingest_url: Betterstack ingest URL
            level: Minimum log level to emit
            timeout: HTTP request timeout in seconds
        """
        super().__init__(level)
        self.token = token
        self.ingest_url = ingest_url
        self.timeout = timeout
        self._client: httpx.Client | None = None

    @classmethod
    def from_config(cls, config: Config) -> BetterstackHandler:
        """
        Create handler from config object.

        Args:
            config: Config instance

        Returns:
            BetterstackHandler instance
        """
        if not config.betterstack_token:
            raise ValueError("betterstack_token is required")

        return cls(
            token=config.betterstack_token,
            ingest_url=config.betterstack_ingest_url,
            level=config.log_level,
        )

    def _get_client(self) -> httpx.Client:
        """
        Lazy initialize HTTP client.

        Returns:
            httpx.Client instance
        """
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def emit(self, payload: dict[str, Any]) -> None:
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
