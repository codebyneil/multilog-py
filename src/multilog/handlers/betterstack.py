"""Betterstack handler for multilog-py."""

import os
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
        token: str | None = None,
        ingest_url: str | None = None,
        level: LogLevel = LogLevel.DEBUG,
        timeout: float = 10.0,
    ):
        """
        Initialize Betterstack handler.

        Args:
            token: Betterstack authentication token (reads from BETTERSTACK_TOKEN env var if not provided)
            ingest_url: Betterstack ingest URL (reads from BETTERSTACK_INGEST_URL env var if not provided)
            level: Minimum log level to emit
            timeout: HTTP request timeout in seconds

        Raises:
            ValueError: If token or ingest_url is not provided and not found in environment variables
        """
        super().__init__(level)

        # Read from environment if not provided
        self.token = token or os.getenv("BETTERSTACK_TOKEN")
        self.ingest_url = ingest_url or os.getenv("BETTERSTACK_INGEST_URL")

        if not self.token:
            raise ValueError("betterstack_token is required (provide as argument or set BETTERSTACK_TOKEN env var)")
        if not self.ingest_url:
            raise ValueError("betterstack_ingest_url is required (provide as argument or set BETTERSTACK_INGEST_URL env var)")

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

        Raises:
            ValueError: If token or ingest_url is missing
        """
        if not config.betterstack_token:
            raise ValueError("betterstack_token is required")
        if not config.betterstack_ingest_url:
            raise ValueError("betterstack_ingest_url is required")

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
